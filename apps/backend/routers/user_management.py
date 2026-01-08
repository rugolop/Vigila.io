"""
User Management API routes.
Handles CRUD operations for users with role-based permissions.

Permissions:
- Admins: Can manage users in their own tenant (cannot create superadmins)
- Superadmins: Can manage users in any tenant (can create superadmins)
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_, or_
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
import secrets
import hashlib

from database import get_db
from models import TenantUser, Tenant, UserRole

router = APIRouter(prefix="/api/users", tags=["user-management"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserCreateRequest(UserBase):
    """Request to create a new user."""
    tenant_id: int
    role: str  # admin, operator, viewer (NOT superadmin for regular admins)
    all_locations_access: bool = False
    password: Optional[str] = None  # For email/password auth


class UserUpdateRequest(BaseModel):
    """Request to update an existing user."""
    name: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[int] = None
    all_locations_access: Optional[bool] = None
    is_active: Optional[bool] = None


class UserDetailResponse(BaseModel):
    """Detailed user information combining Better Auth and TenantUser."""
    id: str
    email: str
    name: Optional[str]
    image: Optional[str]
    
    # Tenant info
    tenant_id: int
    tenant_name: str
    tenant_slug: str
    role: str
    all_locations_access: bool
    is_active: bool
    
    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Simplified user information for lists."""
    id: str
    email: str
    name: Optional[str]
    tenant_id: int
    tenant_name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Helper Functions
# =============================================================================

async def get_current_user_role(user_id: str, db: AsyncSession) -> tuple[str, Optional[int]]:
    """
    Get the current user's role and tenant_id.
    Returns (role, tenant_id).
    Checks Better Auth user table first for superadmin (if table exists).
    """
    # Try to check Better Auth user table for superadmin role
    better_auth_role = None
    try:
        user_role_query = text("SELECT role FROM \"user\" WHERE id = :user_id")
        user_role_result = await db.execute(user_role_query, {"user_id": user_id})
        user_role_row = user_role_result.first()
        better_auth_role = user_role_row[0] if user_role_row else None
    except Exception:
        # Table doesn't exist or query failed - continue with tenant_user
        pass
    
    if better_auth_role == "superadmin":
        return ("superadmin", None)
    
    # Get from tenant_user
    tenant_user = await db.scalar(
        select(TenantUser).where(TenantUser.id == user_id)
    )
    
    if not tenant_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found or not assigned to any tenant"
        )
    
    return (tenant_user.role, tenant_user.tenant_id)


def validate_role_creation(creator_role: str, target_role: str) -> None:
    """
    Validate if the creator can assign the target role.
    
    Rules:
    - Admins can create: admin, operator, viewer (NOT superadmin)
    - Superadmins can create: any role including superadmin
    """
    valid_roles = ["admin", "operator", "viewer", "superadmin"]
    
    if target_role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )
    
    if creator_role == "admin" and target_role == "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot create users with superadmin role"
        )


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("", response_model=List[UserListResponse])
async def list_users(
    tenant_id: Optional[int] = None,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db)
):
    """
    List users.
    
    - Admins: Only see users from their tenant
    - Superadmins: Can filter by tenant_id or see all users
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    current_role, current_tenant_id = await get_current_user_role(x_user_id, db)
    
    # Build query based on permissions
    if current_role == "superadmin":
        # Superadmin can filter by tenant or see all
        if tenant_id:
            query = select(TenantUser, Tenant).join(
                Tenant, TenantUser.tenant_id == Tenant.id
            ).where(TenantUser.tenant_id == tenant_id)
        else:
            query = select(TenantUser, Tenant).join(
                Tenant, TenantUser.tenant_id == Tenant.id
            )
    elif current_role == "admin":
        # Admin can only see their tenant
        query = select(TenantUser, Tenant).join(
            Tenant, TenantUser.tenant_id == Tenant.id
        ).where(TenantUser.tenant_id == current_tenant_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and superadmins can list users"
        )
    
    result = await db.execute(query)
    rows = result.all()
    
    # Get Better Auth user info
    user_ids = [row[0].id for row in rows]
    if user_ids:
        placeholders = ", ".join([f":id{i}" for i in range(len(user_ids))])
        auth_users_query = text(f"""
            SELECT id, email, name, image, "createdAt"
            FROM "user"
            WHERE id IN ({placeholders})
        """)
        params = {f"id{i}": uid for i, uid in enumerate(user_ids)}
        try:
            auth_result = await db.execute(auth_users_query, params)
            auth_users = {row[0]: row for row in auth_result.all()}
        except Exception:
            # Better Auth table doesn't exist - use placeholder data
            auth_users = {uid: (uid, f"user_{uid[:8]}@example.com", "User", None, None) for uid in user_ids}
    else:
        auth_users = {}
    
    # Combine data
    users_list = []
    for tenant_user, tenant in rows:
        auth_user = auth_users.get(tenant_user.id)
        if auth_user:
            users_list.append(UserListResponse(
                id=tenant_user.id,
                email=auth_user[1],
                name=auth_user[2],
                tenant_id=tenant_user.tenant_id,
                tenant_name=tenant.name,
                role=tenant_user.role,
                is_active=tenant_user.is_active,
                created_at=tenant_user.created_at
            ))
    
    return users_list


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed user information.
    
    - Admins: Can only view users from their tenant
    - Superadmins: Can view any user
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    current_role, current_tenant_id = await get_current_user_role(x_user_id, db)
    
    # Get tenant user
    result = await db.execute(
        select(TenantUser, Tenant).join(
            Tenant, TenantUser.tenant_id == Tenant.id
        ).where(TenantUser.id == user_id)
    )
    row = result.first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    tenant_user, tenant = row
    
    # Check permissions
    if current_role == "admin" and tenant_user.tenant_id != current_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view users from your tenant"
        )
    
    # Get Better Auth user info
    auth_user_query = text("""
        SELECT id, email, name, image
        FROM "user"
        WHERE id = :user_id
    """)
    try:
        auth_result = await db.execute(auth_user_query, {"user_id": user_id})
        auth_user = auth_result.first()
    except Exception:
        # Better Auth table doesn't exist - use placeholder
        auth_user = (user_id, f"user_{user_id[:8]}@example.com", "User", None)
    
    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User authentication data not found"
        )
    
    return UserDetailResponse(
        id=tenant_user.id,
        email=auth_user[1],
        name=auth_user[2],
        image=auth_user[3],
        tenant_id=tenant_user.tenant_id,
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        role=tenant_user.role,
        all_locations_access=tenant_user.all_locations_access,
        is_active=tenant_user.is_active,
        created_at=tenant_user.created_at,
        updated_at=tenant_user.updated_at
    )


@router.post("", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreateRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new user.
    
    - Admins: Can create users in their tenant (admin, operator, viewer roles only)
    - Superadmins: Can create users in any tenant (including superadmin role)
    
    Note: This creates both the Better Auth user and TenantUser entries.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    current_role, current_tenant_id = await get_current_user_role(x_user_id, db)
    
    # Validate permissions
    if current_role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and superadmins can create users"
        )
    
    # Validate role assignment
    validate_role_creation(current_role, user_data.role)
    
    # Admins can only create in their own tenant
    if current_role == "admin" and user_data.tenant_id != current_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create users in your own tenant"
        )
    
    # Verify tenant exists
    tenant = await db.get(Tenant, user_data.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check if email already exists in Better Auth
    try:
        check_email_query = text('SELECT id FROM "user" WHERE email = :email')
        existing_email = await db.execute(check_email_query, {"email": user_data.email})
        if existing_email.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists"
            )
    except HTTPException:
        raise
    except Exception:
        # Better Auth table doesn't exist - skip check
        pass
    
    # Generate a secure user ID
    user_id = secrets.token_urlsafe(32)
    
    # Hash password using SHA256 (Better Auth compatible)
    password_hash = None
    if user_data.password:
        password_hash = hashlib.sha256(user_data.password.encode()).hexdigest()
    
    # Create user in Better Auth table
    try:
        create_user_query = text('''
            INSERT INTO "user" (id, email, name, image, "createdAt", "updatedAt")
            VALUES (:id, :email, :name, NULL, NOW(), NOW())
        ''')
        await db.execute(create_user_query, {
            "id": user_id,
            "email": user_data.email,
            "name": user_data.name or user_data.email.split('@')[0]
        })
        
        # Create account entry for email/password auth if password provided
        if password_hash:
            create_account_query = text('''
                INSERT INTO account (id, "userId", "accountId", "providerId", password, "createdAt", "updatedAt")
                VALUES (:account_id, :user_id, :account_id_val, 'credential', :password, NOW(), NOW())
            ''')
            await db.execute(create_account_query, {
                "account_id": secrets.token_urlsafe(32),
                "user_id": user_id,
                "account_id_val": user_data.email,
                "password": password_hash
            })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user in auth system: {str(e)}"
        )
    
    # Create TenantUser entry
    tenant_user = TenantUser(
        id=user_id,
        tenant_id=user_data.tenant_id,
        role=user_data.role,
        all_locations_access=user_data.all_locations_access,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(tenant_user)
    await db.commit()
    await db.refresh(tenant_user)
    
    # Return the created user
    return UserDetailResponse(
        id=user_id,
        email=user_data.email,
        name=user_data.name or user_data.email.split('@')[0],
        image=None,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        role=user_data.role,
        all_locations_access=user_data.all_locations_access,
        is_active=True,
        created_at=tenant_user.created_at,
        updated_at=tenant_user.updated_at
    )


@router.patch("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdateRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a user.
    
    - Admins: Can update users in their tenant (cannot assign superadmin role)
    - Superadmins: Can update any user (including superadmin role)
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    current_role, current_tenant_id = await get_current_user_role(x_user_id, db)
    
    # Validate permissions
    if current_role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and superadmins can update users"
        )
    
    # Get user to update
    result = await db.execute(
        select(TenantUser, Tenant).join(
            Tenant, TenantUser.tenant_id == Tenant.id
        ).where(TenantUser.id == user_id)
    )
    row = result.first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    tenant_user, tenant = row
    
    # Admins can only update users in their tenant
    if current_role == "admin" and tenant_user.tenant_id != current_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update users in your own tenant"
        )
    
    # Validate tenant change (only superadmins)
    if user_update.tenant_id is not None:
        if current_role != "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superadmins can change user tenant"
            )
        
        # Verify new tenant exists
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == user_update.tenant_id)
        )
        new_tenant = tenant_result.scalar_one_or_none()
        if not new_tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        tenant_user.tenant_id = user_update.tenant_id
    
    # Validate role change if provided
    if user_update.role:
        validate_role_creation(current_role, user_update.role)
        tenant_user.role = user_update.role
    
    # Update TenantUser fields
    if user_update.all_locations_access is not None:
        tenant_user.all_locations_access = user_update.all_locations_access
    
    # Update name in Better Auth user table if name provided
    if user_update.name:
        try:
            update_name_query = text("""
                UPDATE "user" 
                SET name = :name, "updatedAt" = NOW()
                WHERE id = :user_id
            """)
            await db.execute(update_name_query, {"name": user_update.name, "user_id": user_id})
        except Exception:
            # Better Auth table doesn't exist - skip update
            pass
    
    await db.commit()
    await db.refresh(tenant_user)
    
    # Get updated tenant info (in case it was changed)
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_user.tenant_id)
    )
    updated_tenant = tenant_result.scalar_one()
    
    # Get updated user info
    auth_user_query = text("""
        SELECT id, email, name, image
        FROM "user"
        WHERE id = :user_id
    """)
    try:
        auth_result = await db.execute(auth_user_query, {"user_id": user_id})
        auth_user = auth_result.first()
    except Exception:
        # Better Auth table doesn't exist - use placeholder
        auth_user = (user_id, f"user_{user_id[:8]}@example.com", user_update.name or "User", None)
    
    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User authentication data not found"
        )
    
    return UserDetailResponse(
        id=tenant_user.id,
        email=auth_user[1],
        name=auth_user[2],
        image=auth_user[3],
        tenant_id=tenant_user.tenant_id,
        tenant_name=updated_tenant.name,
        tenant_slug=updated_tenant.slug,
        role=tenant_user.role,
        all_locations_access=tenant_user.all_locations_access,
        is_active=tenant_user.is_active,
        created_at=tenant_user.created_at,
        updated_at=tenant_user.updated_at
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a user (remove from tenant).
    
    - Admins: Can delete users from their tenant
    - Superadmins: Can delete any user
    
    Note: This only removes the TenantUser entry. 
    The Better Auth user remains and can be reassigned to another tenant.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    current_role, current_tenant_id = await get_current_user_role(x_user_id, db)
    
    # Validate permissions
    if current_role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and superadmins can delete users"
        )
    
    # Prevent self-deletion
    if user_id == x_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own user account"
        )
    
    # Get user to delete
    tenant_user = await db.scalar(
        select(TenantUser).where(TenantUser.id == user_id)
    )
    
    if not tenant_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Admins can only delete users from their tenant
    if current_role == "admin" and tenant_user.tenant_id != current_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete users from your own tenant"
        )
    
    await db.delete(tenant_user)
    await db.commit()
