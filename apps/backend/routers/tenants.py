"""
Tenant management API routes.
Handles CRUD operations for tenants (organizations/clients).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from models import Tenant, TenantUser, Location, Camera, TenantStatus, UserRole

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class TenantBase(BaseModel):
    name: str
    slug: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    max_cameras: int = 10
    max_users: int = 5
    max_locations: int = 3
    storage_quota_gb: int = 100


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    status: Optional[str] = None
    max_cameras: Optional[int] = None
    max_users: Optional[int] = None
    max_locations: Optional[int] = None
    storage_quota_gb: Optional[int] = None


class TenantResponse(BaseModel):
    """Response schema - handles NULL values from DB gracefully"""
    id: int
    name: str
    slug: str
    status: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    max_cameras: int = 10
    max_users: int = 5
    max_locations: int = 3
    storage_quota_gb: int = 100
    created_at: datetime
    updated_at: datetime
    # Stats
    cameras_count: int = 0
    users_count: int = 0
    locations_count: int = 0

    class Config:
        from_attributes = True


class TenantUserBase(BaseModel):
    id: str  # Better Auth user ID
    role: str = UserRole.VIEWER.value
    all_locations_access: bool = False


class TenantUserCreate(TenantUserBase):
    pass


class TenantUserUpdate(BaseModel):
    role: Optional[str] = None
    all_locations_access: Optional[bool] = None
    is_active: Optional[bool] = None


class TenantUserResponse(TenantUserBase):
    tenant_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Tenant CRUD Routes
# =============================================================================

@router.get("", response_model=List[TenantResponse])
async def list_tenants(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all tenants with optional status filter."""
    query = select(Tenant)
    
    if status:
        query = query.where(Tenant.status == status)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    tenants = result.scalars().all()
    
    # Get counts for each tenant
    response = []
    for tenant in tenants:
        # Get counts
        cameras_count = await db.scalar(
            select(func.count(Camera.id)).where(Camera.tenant_id == tenant.id)
        )
        users_count = await db.scalar(
            select(func.count(TenantUser.id)).where(TenantUser.tenant_id == tenant.id)
        )
        locations_count = await db.scalar(
            select(func.count(Location.id)).where(Location.tenant_id == tenant.id)
        )
        
        tenant_data = TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            status=tenant.status,
            contact_email=tenant.contact_email,
            contact_phone=tenant.contact_phone,
            max_cameras=tenant.max_cameras,
            max_users=tenant.max_users,
            max_locations=tenant.max_locations,
            storage_quota_gb=tenant.storage_quota_gb,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            cameras_count=cameras_count or 0,
            users_count=users_count or 0,
            locations_count=locations_count or 0,
        )
        response.append(tenant_data)
    
    return response


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant: TenantCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new tenant/organization."""
    # Check if slug already exists
    existing = await db.scalar(
        select(Tenant).where(Tenant.slug == tenant.slug)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant with slug '{tenant.slug}' already exists"
        )
    
    db_tenant = Tenant(
        name=tenant.name,
        slug=tenant.slug,
        contact_email=tenant.contact_email,
        contact_phone=tenant.contact_phone,
        max_cameras=tenant.max_cameras,
        max_users=tenant.max_users,
        max_locations=tenant.max_locations,
        storage_quota_gb=tenant.storage_quota_gb,
        status=TenantStatus.ACTIVE.value,
    )
    db.add(db_tenant)
    await db.commit()
    await db.refresh(db_tenant)
    
    return TenantResponse(
        id=db_tenant.id,
        name=db_tenant.name,
        slug=db_tenant.slug,
        status=db_tenant.status,
        contact_email=db_tenant.contact_email,
        contact_phone=db_tenant.contact_phone,
        max_cameras=db_tenant.max_cameras,
        max_users=db_tenant.max_users,
        max_locations=db_tenant.max_locations,
        storage_quota_gb=db_tenant.storage_quota_gb,
        created_at=db_tenant.created_at,
        updated_at=db_tenant.updated_at,
        cameras_count=0,
        users_count=0,
        locations_count=0,
    )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific tenant by ID."""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Get counts
    cameras_count = await db.scalar(
        select(func.count(Camera.id)).where(Camera.tenant_id == tenant.id)
    )
    users_count = await db.scalar(
        select(func.count(TenantUser.id)).where(TenantUser.tenant_id == tenant.id)
    )
    locations_count = await db.scalar(
        select(func.count(Location.id)).where(Location.tenant_id == tenant.id)
    )
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        contact_email=tenant.contact_email,
        contact_phone=tenant.contact_phone,
        max_cameras=tenant.max_cameras,
        max_users=tenant.max_users,
        max_locations=tenant.max_locations,
        storage_quota_gb=tenant.storage_quota_gb,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        cameras_count=cameras_count or 0,
        users_count=users_count or 0,
        locations_count=locations_count or 0,
    )


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: int,
    tenant_update: TenantUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a tenant."""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    update_data = tenant_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tenant, key, value)
    
    await db.commit()
    await db.refresh(tenant)
    
    # Get counts
    cameras_count = await db.scalar(
        select(func.count(Camera.id)).where(Camera.tenant_id == tenant.id)
    )
    users_count = await db.scalar(
        select(func.count(TenantUser.id)).where(TenantUser.tenant_id == tenant.id)
    )
    locations_count = await db.scalar(
        select(func.count(Location.id)).where(Location.tenant_id == tenant.id)
    )
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        contact_email=tenant.contact_email,
        contact_phone=tenant.contact_phone,
        max_cameras=tenant.max_cameras,
        max_users=tenant.max_users,
        max_locations=tenant.max_locations,
        storage_quota_gb=tenant.storage_quota_gb,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        cameras_count=cameras_count or 0,
        users_count=users_count or 0,
        locations_count=locations_count or 0,
    )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a tenant and all associated data."""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Prevent deleting default tenant
    if tenant.slug == "default":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete default tenant"
        )
    
    await db.delete(tenant)
    await db.commit()


# =============================================================================
# Tenant Users Management
# =============================================================================

@router.get("/{tenant_id}/users", response_model=List[TenantUserResponse])
async def list_tenant_users(
    tenant_id: int,
    db: AsyncSession = Depends(get_db)
):
    """List all users in a tenant."""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    result = await db.execute(
        select(TenantUser).where(TenantUser.tenant_id == tenant_id)
    )
    users = result.scalars().all()
    return users


@router.post("/{tenant_id}/users", response_model=TenantUserResponse, status_code=status.HTTP_201_CREATED)
async def add_user_to_tenant(
    tenant_id: int,
    user: TenantUserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a user to a tenant."""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check if user already exists in this tenant
    existing = await db.scalar(
        select(TenantUser).where(
            TenantUser.id == user.id,
            TenantUser.tenant_id == tenant_id
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already belongs to this tenant"
        )
    
    # Check user limit
    users_count = await db.scalar(
        select(func.count(TenantUser.id)).where(TenantUser.tenant_id == tenant_id)
    )
    if users_count >= tenant.max_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant has reached maximum users limit ({tenant.max_users})"
        )
    
    db_user = TenantUser(
        id=user.id,
        tenant_id=tenant_id,
        role=user.role,
        all_locations_access=user.all_locations_access,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user


@router.patch("/{tenant_id}/users/{user_id}", response_model=TenantUserResponse)
async def update_tenant_user(
    tenant_id: int,
    user_id: str,
    user_update: TenantUserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a user's role or permissions in a tenant."""
    user = await db.scalar(
        select(TenantUser).where(
            TenantUser.id == user_id,
            TenantUser.tenant_id == tenant_id
        )
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this tenant"
        )
    
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/{tenant_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_tenant(
    tenant_id: int,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Remove a user from a tenant."""
    user = await db.scalar(
        select(TenantUser).where(
            TenantUser.id == user_id,
            TenantUser.tenant_id == tenant_id
        )
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this tenant"
        )
    
    await db.delete(user)
    await db.commit()
