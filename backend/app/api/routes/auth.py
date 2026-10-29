import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import (
    AUTH_COOKIE_NAME,
    AUTH_COOKIE_SECURE,
    AUTH_REMEMBER_SECONDS,
    AUTH_SESSION_SECONDS,
)
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.db.database import get_db
from app.models.user import User
from app.models.auth_session import AuthSession
from app.models.organization import Organization
from app.schemas.auth import AuthUser, LoginRequest, LoginResponse, PasswordChangeRequest
from app.services.security.login_throttle import clear_account_failures, record_failure, retry_after, throttle_keys
from app.services.operations.security_audit import audit_security_event
from app.core.rate_limit import auth_limiter, rate_limit
from app.core.demo import DEMO_ENABLED, DEMO_QUESTION_LIMIT, DEMO_SESSION_SECONDS, enforce_demo_access
from app.services.application.demo_service import create_demo_guest

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def _request_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token is None and credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    return token


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def revoke_user_sessions(db: Session, user_id: UUID, *, except_id: UUID | None = None) -> None:
    """Revoke every active session for a user, optionally keeping one alive.

    Used on logout-of-other-devices paths such as password change and account
    deactivation, so a stolen cookie cannot outlive those events.
    """
    statement = (
        update(AuthSession)
        .where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    if except_id is not None:
        statement = statement.where(AuthSession.id != except_id)
    db.execute(statement)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = _request_token(request, credentials)
    if token is None:
        raise unauthorized
    payload = decode_access_token(token)
    if payload is None or not payload.get("sub") or not payload.get("jti"):
        raise unauthorized
    try:
        user_id = UUID(str(payload["sub"]))
        session_id = UUID(str(payload["jti"]))
    except ValueError as exc:
        raise unauthorized from exc
    auth_session = db.get(AuthSession, session_id)
    if (
        auth_session is None
        or auth_session.user_id != user_id
        or auth_session.revoked_at is not None
        or _aware_utc(auth_session.expires_at) <= datetime.now(timezone.utc)
    ):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    enforce_demo_access(request, user)
    return user


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(rate_limit(auth_limiter))])
def login(payload: LoginRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    organization_slug = payload.organization.strip().lower()
    username = payload.username.strip()
    client_ip = request.client.host if request.client else "unknown"
    keys = throttle_keys(organization_slug, username, client_ip)
    wait_seconds = retry_after(db, keys)
    if wait_seconds is not None:
        audit_security_event("login", "blocked", client_ip=client_ip, reason="account_throttled")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts. Try again later.", headers={"Retry-After": str(wait_seconds)})
    organization = db.scalar(select(Organization).where(Organization.slug == organization_slug))
    user = db.scalar(select(User).where(User.username == username, User.organization_id == organization.id)) if organization else None
    if user is None or getattr(user, "is_demo", False) or not verify_password(payload.password, user.password_hash):
        lock_seconds = record_failure(db, keys)
        audit_security_event("login", "denied", client_ip=client_ip, reason="invalid_credentials")
        logger.warning("Login failed", extra={"account_key": keys[0], "ip_key": keys[1], "locked_seconds": lock_seconds})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.is_active:
        audit_security_event("login", "denied", actor_id=str(user.id), client_ip=client_ip, reason="inactive_account")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    clear_account_failures(db, keys[0])
    audit_security_event("login", "allowed", actor_id=str(user.id), client_ip=client_ip)

    expires_in = AUTH_REMEMBER_SECONDS if payload.remember_me else AUTH_SESSION_SECONDS
    return _start_session(db, response, user, organization, expires_in, remember_me=payload.remember_me)


def _start_session(db: Session, response: Response, user: User, organization: Organization, expires_in: int, *, remember_me: bool = False) -> LoginResponse:
    session_id = uuid4()
    db.add(
        AuthSession(
            id=session_id,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        )
    )
    db.commit()
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=create_access_token(str(user.id), user.role, expires_in, str(session_id)),
        max_age=expires_in if remember_me else None,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(
        expires_in=expires_in,
        user=AuthUser(id=user.id, username=user.username, role=user.role, organization_id=organization.id, organization_name=organization.name, organization_slug=organization.slug, is_demo=getattr(user, "is_demo", False)),
    )


@router.get("/demo")
def demo_availability(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"enabled": DEMO_ENABLED, "question_limit": DEMO_QUESTION_LIMIT, "session_seconds": DEMO_SESSION_SECONDS}


@router.post("/demo", response_model=LoginResponse, dependencies=[Depends(rate_limit(auth_limiter))])
def demo_login(response: Response, request: Request, db: Session = Depends(get_db)):
    if not DEMO_ENABLED:
        raise HTTPException(404, "Not found")
    try:
        user, organization = create_demo_guest(db, request)
        return _start_session(db, response, user, organization, DEMO_SESSION_SECONDS)
    except Exception:
        db.rollback()
        raise


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    token = _request_token(request, credentials)
    payload = decode_access_token(token) if token else None
    if payload and payload.get("jti"):
        try:
            session_id = UUID(str(payload["jti"]))
        except ValueError:
            session_id = None
        if session_id is not None:
            db.execute(
                update(AuthSession)
                .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=datetime.now(timezone.utc))
            )
            db.commit()
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    user.password_hash = hash_password(payload.new_password)

    token = _request_token(request, credentials)
    decoded = decode_access_token(token) if token else None
    current_session_id = None
    if decoded and decoded.get("jti"):
        try:
            current_session_id = UUID(str(decoded["jti"]))
        except ValueError:
            current_session_id = None
    # Keep the requesting device signed in but invalidate every other session.
    revoke_user_sessions(db, user.id, except_id=current_session_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AuthUser)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    organization = db.get(Organization, user.organization_id)
    return AuthUser(id=user.id, username=user.username, role=user.role, organization_id=user.organization_id, organization_name=organization.name, organization_slug=organization.slug, is_demo=getattr(user, "is_demo", False))


@router.get("/avatar")
def get_avatar(user: User = Depends(get_current_user)):
    from app.core.config import UPLOAD_DIR
    from fastapi.responses import FileResponse
    path = UPLOAD_DIR.parent / "avatars" / f"{user.id}.png"
    if not path.is_file():
        raise HTTPException(404, "Avatar not found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.put("/avatar")
async def put_avatar(request: Request, user: User = Depends(get_current_user)):
    import io
    import os
    import tempfile
    from PIL import Image, UnidentifiedImageError
    from app.core.config import UPLOAD_DIR
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(413, "Image must be under 5 MB")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"} or image.width * image.height > 25_000_000:
                raise ValueError("Invalid image")
            from PIL import ImageOps
            avatar = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGBA"), (192, 192))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(400, "Invalid image") from None
    directory = UPLOAD_DIR.parent / "avatars"
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=directory, suffix=".png")
    try:
        with os.fdopen(fd, "wb") as output:
            avatar.save(output, format="PNG")
        os.replace(temporary, directory / f"{user.id}.png")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"saved": True}


@router.delete("/avatar")
def delete_avatar(user: User = Depends(get_current_user)):
    from app.core.config import UPLOAD_DIR
    (UPLOAD_DIR.parent / "avatars" / f"{user.id}.png").unlink(missing_ok=True)
    return Response(status_code=204)
