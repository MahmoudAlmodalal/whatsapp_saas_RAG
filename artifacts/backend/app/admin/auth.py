"""
app/admin/auth.py
──────────────────
SQLAdmin authentication backend.

Only users with `role == 'super_admin'` can access the admin panel.
Uses secure cookie-based sessions (itsdangerous signed).
"""
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import get_settings
from app.models.user import User, UserRole
from app.core.security import verify_password, create_access_token


class AdminAuth(AuthenticationBackend):
    """
    Cookie-based auth for the SQLAdmin panel.
    Only super_admin users are allowed through.
    """

    async def login(self, request: Request) -> bool:
        """
        Called when the admin login form is submitted.
        Returns True to allow access, False to reject.
        """
        form = await request.form()
        email = str(form.get("username", ""))
        password = str(form.get("password", ""))

        settings = get_settings()
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with Session() as session:
                result = await session.execute(
                    select(User).where(User.email == email)
                )
                user: User | None = result.scalar_one_or_none()

                if not user:
                    return False
                if user.role != UserRole.super_admin:
                    return False
                if not user.is_active:
                    return False
                if not verify_password(password, user.hashed_password):
                    return False

                # Store a signed token in the session cookie
                token = create_access_token(user.id, user.tenant_id, user.role.value)
                request.session.update({
                    "admin_token": token,
                    "admin_email": user.email,
                    "admin_user_id": str(user.id),
                })
                return True
        finally:
            await engine.dispose()

    async def logout(self, request: Request) -> bool:
        """Clear the admin session."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """
        Called on every admin panel request to verify the session is still valid.
        Returns True if the session is valid, False to redirect to login.
        """
        token = request.session.get("admin_token")
        if not token:
            return False

        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(token)
            return payload.get("role") == UserRole.super_admin.value
        except Exception:
            request.session.clear()
            return False
