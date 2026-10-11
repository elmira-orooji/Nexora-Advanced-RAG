import hashlib
import hmac
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, parse_qsl, quote, urlencode
from urllib.request import Request
from collections.abc import Iterator
from pathlib import Path
from . import transport
from .contracts import ConnectorSyncError, SourceSnapshot, ALLOWED_EXTENSIONS
from .contracts import MAX_REMOTE_BYTES

def _aws_signed_get(url: str, credentials: dict[str, str]) -> bytes:
    access_key_id = credentials.get("access_key_id", ""); secret_access_key = credentials.get("secret_access_key", ""); region = credentials.get("region", "")
    if not all((access_key_id, secret_access_key, region)):
        raise ConnectorSyncError("S3 credentials or region are missing for this organization")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".amazonaws.com"):
        raise ConnectorSyncError("S3 requests must use an AWS HTTPS endpoint")
    now = datetime.now(timezone.utc); amz_date = now.strftime("%Y%m%dT%H%M%SZ"); date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(b"").hexdigest(); host = parsed.netloc
    canonical_query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), quote_via=quote, safe="-_.~")
    canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(("GET", quote(parsed.path or "/", safe="/-_.~"), canonical_query, canonical_headers, signed_headers, payload_hash))
    scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(("AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode()).hexdigest()))
    sign = lambda key, value: hmac.new(key, value.encode(), hashlib.sha256).digest()
    signing_key = sign(sign(sign(sign(("AWS4" + secret_access_key).encode(), date_stamp), region), "s3"), "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = f"AWS4-HMAC-SHA256 Credential={access_key_id}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
    try:
        with transport._public_urlopen(Request(url, headers={"Authorization": authorization, "x-amz-date": amz_date, "x-amz-content-sha256": payload_hash}), timeout=30) as response:
            data = response.read(MAX_REMOTE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc: raise ConnectorSyncError("S3 request failed") from exc
    if len(data) > MAX_REMOTE_BYTES: raise ConnectorSyncError("S3 response or file exceeds the 2 MB limit")
    return data


def _s3(source_url: str, credentials: dict[str, str]) -> SourceSnapshot:
    parsed = urlparse(source_url); host = (parsed.hostname or "").lower(); path = parsed.path.lstrip("/")
    virtual = re.fullmatch(r"([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])\.s3(?:\.[a-z0-9-]+)?\.amazonaws\.com", host)
    if virtual: bucket, prefix = virtual.group(1), path
    else:
        regional = re.fullmatch(r"s3(?:\.[a-z0-9-]+)?\.amazonaws\.com", host)
        parts = path.split("/", 1)
        if not regional or not parts[0]: raise ConnectorSyncError("Use an S3 HTTPS URL such as https://bucket.s3.region.amazonaws.com/prefix")
        bucket, prefix = parts[0], parts[1] if len(parts) > 1 else ""
    region = credentials.get("region", "")
    if not region: raise ConnectorSyncError("S3 region is missing for this organization")
    endpoint = f"https://{bucket}.s3.{region}.amazonaws.com"

    snapshot = SourceSnapshot(source_iterator=iter([]))

    def _iter() -> Iterator[tuple[str, str, str, str]]:
        continuation_token: str | None = None
        complete = True
        while True:
            params: dict[str, str] = {"list-type": "2", "prefix": prefix, "max-keys": "100"}
            if continuation_token:
                params["continuation-token"] = continuation_token
            listing = _aws_signed_get(f"{endpoint}/?{urlencode(params)}", credentials)
            try: root = ET.fromstring(listing)
            except ET.ParseError as exc: raise ConnectorSyncError("S3 returned invalid object metadata") from exc
            nodes = root.findall("{*}Contents")
            for node in nodes:
                key = node.findtext("{*}Key") or ""
                snapshot.observed_ids.add(key)
                if Path(key).suffix.lower() not in ALLOWED_EXTENSIONS: continue
                object_url = f"{endpoint}/{quote(key, safe='/')}"; body = _aws_signed_get(object_url, credentials)
                text = body.decode("utf-8", errors="replace").strip()
                if len(text) >= 20:
                    yield (key, Path(key).name[:255], text, object_url)
            is_truncated = root.findtext("{*}IsTruncated") == "true"
            if is_truncated:
                next_token = root.findtext("{*}NextContinuationToken")
                if next_token:
                    continuation_token = next_token
                else:
                    complete = False
                    break
            else:
                break
        snapshot.complete = complete

    snapshot.source_iterator = _iter()
    return snapshot
