"""
backend/routers/auth_router.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import (
    create_access_token,
    generate_api_key,
    get_current_user,
    hash_password,
    verify_password,
)
from backend.config import get_settings
from backend.database import get_db
from backend.models import APIKey, Subscription, User
from backend.schemas import (
    APIKeyCreate,
    APIKeyCreated,
    APIKeyOut,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserOut,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.flush()
    db.add(Subscription(user_id=user.id))
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/api-keys", response_model=APIKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: APIKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreated:
    plaintext, prefix, hashed = generate_api_key()
    key = APIKey(user_id=user.id, name=payload.name, key_prefix=prefix, hashed_key=hashed)
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return APIKeyCreated(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        is_active=key.is_active,
        created_at=key.created_at,
        plaintext_key=plaintext,
    )


@router.get("/api-keys", response_model=list[APIKeyOut])
async def list_api_keys(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[APIKey]:
    result = await db.execute(select(APIKey).where(APIKey.user_id == user.id))
    return list(result.scalars().all())


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    key = await db.get(APIKey, key_id)
    if not key or key.user_id != user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    await db.commit()
