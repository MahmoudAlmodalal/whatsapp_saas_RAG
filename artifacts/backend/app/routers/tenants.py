from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tenants import Tenant
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantResponse, TenantConfigUpdate
from app.core.dependencies import get_current_operator, get_current_admin
from app.core.cache import set_tenant_phone_mapping, get_tenant_id_by_phone

router = APIRouter(tags=["tenants"])

@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_in: TenantCreate,
    current_user_and_tenant: tuple[User, UUID] = Depends(get_current_operator),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new tenant record (operator only).
    """
    if tenant_in.whatsapp_number:
        # Check if whatsapp_number is already mapped in Redis or DB
        existing_mapping = await get_tenant_id_by_phone(tenant_in.whatsapp_number)
        if existing_mapping:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="رقم الواتساب مسجل مسبقاً",
            )
        
        # Check in DB to be safe
        result = await db.execute(
            select(Tenant).where(Tenant.whatsapp_number == tenant_in.whatsapp_number)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="رقم الواتساب مسجل مسبقاً",
            )

    new_tenant = Tenant(
        name=tenant_in.name,
        whatsapp_number=tenant_in.whatsapp_number,
        subscription_tier=tenant_in.subscription_tier,
    )
    db.add(new_tenant)
    await db.commit()
    await db.refresh(new_tenant)

    if new_tenant.whatsapp_number:
        await set_tenant_phone_mapping(new_tenant.whatsapp_number, str(new_tenant.id))

    return new_tenant

@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    current_user_and_tenant: tuple[User, UUID] = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Get tenant details (admin of that tenant only).
    """
    user, user_tenant_id = current_user_and_tenant
    
    if user_tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا تملك صلاحية الوصول لهذه الشركة",
        )

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="الشركة غير موجودة",
        )
        
    return tenant

@router.put("/{tenant_id}/config", response_model=TenantResponse)
async def update_tenant_config(
    tenant_id: UUID,
    config_update: TenantConfigUpdate,
    current_user_and_tenant: tuple[User, UUID] = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Update tenant AI config (admin of that tenant only).
    """
    user, user_tenant_id = current_user_and_tenant
    
    if user_tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا تملك صلاحية الوصول لهذه الشركة",
        )

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="الشركة غير موجودة",
        )

    # Update config JSONB field
    current_config = dict(tenant.config)
    update_data = config_update.model_dump(exclude_unset=True)
    current_config.update(update_data)
    
    tenant.config = current_config
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return tenant

@router.put("/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: UUID,
    current_user_and_tenant: tuple[User, UUID] = Depends(get_current_operator),
    db: AsyncSession = Depends(get_db),
):
    """
    Suspend a tenant (operator only).
    """
    user, _ = current_user_and_tenant
    
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="الشركة غير موجودة",
        )
        
    tenant.is_active = False
    db.add(tenant)
    await db.commit()
    
    return {"message": "Tenant suspended"}
