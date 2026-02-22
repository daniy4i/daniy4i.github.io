from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from jose import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import ApiToken, Organization, User

security = HTTPBearer()


@dataclass
class AuthContext:
    user_id: int
    org_id: int
    auth_type: str


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token(username: str, user_id: int, org_id: int) -> str:
    payload = {
        "sub": username,
        "uid": user_id,
        "org_id": org_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def issue_api_token() -> str:
    return f"nti_{secrets.token_urlsafe(32)}"


def ensure_default_admin() -> None:
    db = SessionLocal()
    try:
        org = db.scalars(select(Organization).where(Organization.name == "Default Org")).first()
        if not org:
            org = Organization(name="Default Org")
            db.add(org)
            db.flush()
        user = db.scalars(select(User).where(User.username == "admin")).first()
        if not user:
            user = User(org_id=org.id, username="admin", password="admin", role="admin")
            db.add(user)
        db.commit()
    finally:
        db.close()


def authenticate_user(username: str, password: str) -> tuple[User, Organization] | None:
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.username == username)).first()
        if not user or user.password != password:
            return None
        org = db.get(Organization, user.org_id)
        if not org:
            return None
        return user, org
    finally:
        db.close()


def require_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> AuthContext:
    token = creds.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return AuthContext(
            user_id=int(payload.get("uid", 1)),
            org_id=int(payload.get("org_id", 1)),
            auth_type="jwt",
        )
    except Exception:
        pass

    db = SessionLocal()
    try:
        hashed = token_hash(token)
        row = db.scalars(select(ApiToken).where(ApiToken.token_hash == hashed, ApiToken.revoked_at.is_(None))).first()
        if row:
            return AuthContext(user_id=0, org_id=row.org_id, auth_type="api_token")
    finally:
        db.close()

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
