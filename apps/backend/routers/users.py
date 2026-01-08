"""
Current user API route.
Returns the tenant user info for the authenticated user.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import Optional
from pydantic import BaseModel

from database import get_db
from models import TenantUser, Tenant

router = APIRouter(prefix="/api/me", tags=["current-user"])


class CurrentUserResponse(BaseModel):
    id: str
    tenant_id: int
    tenant_name: str
    tenant_slug: str
    role: str
    all_locations_access: bool
    is_active: bool

    class Config:
        from_attributes = True


@router.get("", response_model=Optional[CurrentUserResponse])
async def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current user's tenant information.
    
    The user ID is passed from the frontend via the X-User-Id header.
    """
    if not x_user_id:
        return None
    
    # Find the user in tenant_users
    result = await db.execute(
        select(TenantUser, Tenant)
        .join(Tenant, TenantUser.tenant_id == Tenant.id)
        .where(TenantUser.id == x_user_id)
    )
    row = result.first()
    
    if not row:
        return None
    
    tenant_user, tenant = row
    
    # Try to check Better Auth's user table for superadmin role
    # This is optional and will fail gracefully if the table doesn't exist
    better_auth_role = None
    try:
        user_role_query = text("SELECT role FROM \"user\" WHERE id = :user_id")
        user_role_result = await db.execute(user_role_query, {"user_id": x_user_id})
        user_role_row = user_role_result.first()
        better_auth_role = user_role_row[0] if user_role_row else None
    except Exception:
        # Table doesn't exist or query failed - use tenant_user role
        pass
    
    # Use superadmin role from Better Auth if set, otherwise use tenant_user role
    effective_role = better_auth_role if better_auth_role == "superadmin" else tenant_user.role
    
    return CurrentUserResponse(
        id=tenant_user.id,
        tenant_id=tenant_user.tenant_id,
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        role=effective_role,
        all_locations_access=tenant_user.all_locations_access,
        is_active=tenant_user.is_active,
    )


@router.post("/assign-to-tenant")
async def assign_user_to_default_tenant(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db)
):
    """
    Assign a new user to the default tenant as viewer.
    
    This is called when a new user logs in for the first time.
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
    
    # Check if user already exists
    existing = await db.scalar(
        select(TenantUser).where(TenantUser.id == x_user_id)
    )
    if existing:
        return {"message": "User already assigned to a tenant", "tenant_id": existing.tenant_id}
    
    # Find default tenant
    default_tenant = await db.scalar(
        select(Tenant).where(Tenant.slug == "default")
    )
    
    if not default_tenant:
        # Create default tenant if it doesn't exist
        default_tenant = Tenant(
            name="Organización por Defecto",
            slug="default",
            max_cameras=100,
            max_users=100,
            max_locations=50,
            storage_quota_gb=1000,
        )
        db.add(default_tenant)
        await db.commit()
        await db.refresh(default_tenant)
    
    # Create tenant user
    tenant_user = TenantUser(
        id=x_user_id,
        tenant_id=default_tenant.id,
        role="viewer",  # Default role for new users
        all_locations_access=False,
        is_active=True,
    )
    db.add(tenant_user)
    await db.commit()
    
    return {
        "message": "User assigned to default tenant",
        "tenant_id": default_tenant.id,
        "role": "viewer"
    }
