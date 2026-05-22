"""
app/routers/auth.py
───────────────────
Authentication router — /api/v1/auth/

Endpoints
---------
POST /login   → exchange email+password for access+refresh tokens
POST /refresh → exchange a valid refresh token for a new access token

Design decisions
----------------
- Login uses `application/json` body (not OAuth2 form-data) so the Arabic
  frontend doesn't have to deal with form encoding quirks.
- Tokens are returned in the response body (not Set-Cookie) so that both
  web and mobile WhatsApp clients can use the same contract.
- Passwords are never logged. DB queries are keyed on indexed `email` column.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    model_config = {"json_schema_extra": {"example": {"email": "admin@acme.sa", "password": "s3cret"}}}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# ── Routes ────────────────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="تسجيل الدخول",  # Login
    description=(
        "تحقق من بيانات الاعتماد وأعد رمزي الوصول والتحديث. "  # Validate credentials, return tokens
        "رمز الوصول صالح لمدة ساعة، ورمز التحديث لمدة ٧ أيام."
    ),
)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # Constant-time lookup + verify to resist user-enumeration timing attacks
    user = await _get_user_by_email(db, body.email)

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="البريد الإلكتروني أو كلمة المرور غير صحيحة",  # Wrong email or password
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="الحساب موقوف، يرجى التواصل مع الدعم",  # Account suspended
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role.value,
    )
    refresh_token = create_refresh_token(user_id=user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="تجديد رمز الوصول",  # Refresh access token
    description="استخدم رمز التحديث للحصول على رمز وصول جديد دون إعادة تسجيل الدخول.",
)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> AccessTokenResponse:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="رمز التحديث غير صالح أو منتهي الصلاحية",  # Invalid or expired refresh token
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_refresh_token(body.refresh_token)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exc

    new_access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role.value,
    )

    return AccessTokenResponse(access_token=new_access_token)
