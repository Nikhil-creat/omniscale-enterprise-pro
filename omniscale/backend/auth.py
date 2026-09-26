"""
backend/auth.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

Password hashing, JWT issuance/verification, and API-key hashing helpers,
plus the FastAPI dependency that resolves the current authenticated user
from either a bearer JWT or an `X-API-Key` header.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.database import get_db
from backend.models import APIKey, User

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("missing subject")
        return user_id
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc


def generate_api_key() -> tuple[str, str, str]:
    """Returns (plaintext_key, prefix, hashed_key)."""
    plaintext = f"osk_{secrets.token_urlsafe(32)}"
    prefix = plaintext[:12]
    hashed = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, prefix, hashed


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


async def _load_user_with_subscription(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(
        select(User).options(selectinload(User.subscription)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_api_key: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if x_api_key:
        hashed = hash_api_key(x_api_key)
        result = await db.execute(
            select(APIKey).where(APIKey.hashed_key == hashed, APIKey.is_active.is_(True))
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        user = await _load_user_with_subscription(db, api_key.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Inactive or unknown user")
        return user

    if credentials:
        user_id = decode_access_token(credentials.credentials)
        user = await _load_user_with_subscription(db, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Inactive or unknown user")
        return user

    raise HTTPException(status_code=401, detail="Not authenticated")
