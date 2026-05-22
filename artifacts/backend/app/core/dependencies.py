"""
app/core/dependencies.py
────────────────────────
FastAPI reusable dependency functions.

Dependency tree
---------------
get_db                  → yields AsyncSession
  └─ get_current_user   → decodes JWT → returns User ORM object
       ├─ get_current_admin         → asserts role == 'admin' + sets RLS context
       ├─ get_current_agent         → asserts role in {admin, agent} + sets RLS
       └─ get_current_any_role      → any active user + sets RLS context

RLS context is set via `SET LOCAL app.current_tenant = '<uuid>'` so that every
subsequent query in the same transaction is automatically row-filtered.
"""
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, set_tenant_context
from app.models.user import User, UserRole
from app.core.security import decode_access_token

# Swagger UI will show a lock icon and send `Authorization: Bearer <token>`
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Token → User ──────────────────────────────────────────────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the Bearer token, load the matching User row, and return it.

    Raises 401 for any token problem (invalid signature, expired, wrong type).
    Raises 401 if the user no longer exists or is deactivated.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="بيانات الاعتماد غير صالحة أو انتهت صلاحيتها",  # Invalid/expired credentials
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="المستخدم غير موجود",  # User not found
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="الحساب موقوف، يرجى التواصل مع الدعم",  # Account suspended
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ── RLS + role helpers ────────────────────────────────────────────────────────
async def _set_rls_and_return(
    user: User,
    db: AsyncSession,
) -> tuple[User, UUID]:
    """Internal helper: set Postgres RLS context and return (user, tenant_id)."""
    await set_tenant_context(db, str(user.tenant_id))
    return user, user.tenant_id


async def get_current_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, UUID]:
    """
    Require `role == 'admin'`, then activate RLS for the tenant.

    Returns: (User, tenant_id)
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذه العملية تتطلب صلاحيات المدير",  # Admin privileges required
        )
    return await _set_rls_and_return(current_user, db)


async def get_current_agent(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, UUID]:
    """
    Require `role in {admin, agent}`, then activate RLS.

    Operators (read-only) are excluded — use `get_current_any_role` for them.
    Returns: (User, tenant_id)
    """
    if current_user.role == UserRole.operator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ليس لديك صلاحية تعديل البيانات",  # No write permission
        )
    return await _set_rls_and_return(current_user, db)


async def get_current_any_role(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, UUID]:
    """
    Allow any active user regardless of role, then activate RLS.

    Returns: (User, tenant_id)
    """
    return await _set_rls_and_return(current_user, db)


async def get_current_operator(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, UUID]:
    """
    Require `role == 'operator'`, then activate RLS.
    Returns: (User, tenant_id)
    """
    if current_user.role != UserRole.operator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذه العملية تتطلب صلاحيات المشغل (operator)",
        )
    return await _set_rls_and_return(current_user, db)


# Convenience alias kept for backward compat with TASK-003 spec
get_current_tenant_admin = get_current_admin
