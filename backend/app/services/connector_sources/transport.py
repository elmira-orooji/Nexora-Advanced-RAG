import ipaddress
import json
import socket
from http.client import HTTPSConnection
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlencode
from urllib.request import Request, HTTPSHandler, HTTPRedirectHandler, ProxyHandler, build_opener
from .contracts import ConnectorSyncError, MAX_REMOTE_BYTES

def _validate_public_url(value: str, github_only: bool = False) -> list:
    try:
        parsed = urlparse(value)
        port = parsed.port or 443
    except ValueError as exc:
        raise ConnectorSyncError("Invalid source URL") from exc
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ConnectorSyncError("Only public HTTPS URLs are allowed")
    if github_only and parsed.hostname.lower() != "github.com":
        raise ConnectorSyncError("GitHub connectors require a github.com repository URL")
    try: addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc: raise ConnectorSyncError("Could not resolve the source host") from exc
    if not addresses:
        raise ConnectorSyncError("Could not resolve the source host")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global or ip.is_multicast: raise ConnectorSyncError("Private or local network addresses are not allowed")
    return addresses


class _PublicHTTPSConnection(HTTPSConnection):
    def connect(self):
        if self._tunnel_host:
            raise ConnectorSyncError("Connector proxy tunnels are not allowed")
        host = f"[{self.host}]" if ":" in self.host else self.host
        addresses = _validate_public_url(f"https://{host}:{self.port}")
        # Connect to the checked sockaddr directly: never resolve the hostname again.
        for index, (family, socktype, proto, _, sockaddr) in enumerate(addresses):
            sock = socket.socket(family, socktype, proto)
            try:
                sock.settimeout(self.timeout)
                sock.connect(sockaddr)
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except OSError:
                sock.close()
                if index == len(addresses) - 1:
                    raise


class _PublicHTTPSHandler(HTTPSHandler):
    def https_open(self, request):
        return self.do_open(_PublicHTTPSConnection, request, context=self._context)


class _PublicRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        _validate_public_url(newurl)
        # Do not forward bearer tokens, signed headers, or OAuth bodies on redirects.
        if request.has_header("Authorization") or request.data is not None:
            raise ConnectorSyncError("Authenticated connector redirects are not allowed")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def _public_urlopen(request: Request, timeout: int):
    _validate_public_url(request.full_url)
    # Environment proxies could resolve the target independently of our checks.
    opener = build_opener(ProxyHandler({}), _PublicHTTPSHandler(), _PublicRedirectHandler())
    return opener.open(request, timeout=timeout)


def _fetch(url: str, accept: str = "text/plain,text/html,application/json") -> tuple[bytes, str, str]:
    _validate_public_url(url)
    request = Request(url, headers={"User-Agent": "KnowledgeFlow-Connector/1.0", "Accept": accept})
    try:
        with _public_urlopen(request, timeout=20) as response:
            final_url = response.geturl(); _validate_public_url(final_url)
            content_type = response.headers.get_content_type(); data = response.read(MAX_REMOTE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc: raise ConnectorSyncError("Could not download the source") from exc
    if len(data) > MAX_REMOTE_BYTES: raise ConnectorSyncError("Remote content exceeds the 2 MB limit")
    return data, content_type, final_url


def _authorized_json(url: str, token: str) -> dict:
    _validate_public_url(url)
    try:
        with _public_urlopen(Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}), timeout=30) as response:
            return json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ConnectorSyncError("Cloud provider request failed") from exc


def _oauth_token(url: str, values: dict[str, str]) -> str:
    try:
        with _public_urlopen(Request(url, data=urlencode(values).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=30) as response:
            token = json.loads(response.read().decode()).get("access_token")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ConnectorSyncError("Could not authenticate with the cloud provider") from exc
    if not token: raise ConnectorSyncError("Cloud provider returned no access token")
    return token


def _bearer_download(url: str, token: str) -> bytes:
    _validate_public_url(url)
    try:
        with _public_urlopen(Request(url, headers={"Authorization": f"Bearer {token}"}), timeout=30) as response: data = response.read(MAX_REMOTE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc: raise ConnectorSyncError("Could not download cloud file") from exc
    if len(data) > MAX_REMOTE_BYTES: raise ConnectorSyncError("Cloud file exceeds the 2 MB limit")
    return data
