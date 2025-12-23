"""
Location management API routes.
Handles CRUD operations for locations (physical sites with cameras).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from models import Location, Tenant, Camera, TenantUser, user_locations

router = APIRouter(prefix="/api/locations", tags=["locations"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class LocationBase(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    timezone: str = "UTC"


class LocationCreate(LocationBase):
    tenant_id: int


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class LocationResponse(LocationBase):
    id: int
    tenant_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    cameras_count: int = 0

    class Config:
        from_attributes = True


class LocationWithCameras(LocationResponse):
    cameras: List[dict] = []


# =============================================================================
# Location CRUD Routes
# =============================================================================

@router.get("", response_model=List[LocationResponse])
async def list_locations(
    tenant_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all locations, optionally filtered by tenant."""
    query = select(Location)
    
    if tenant_id:
        query = query.where(Location.tenant_id == tenant_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    locations = result.scalars().all()
    
    # Get cameras count for each location
    response = []
    for location in locations:
        cameras_count = await db.scalar(
            select(func.count(Camera.id)).where(Camera.location_id == location.id)
        )
        
        location_data = LocationResponse(
            id=location.id,
            tenant_id=location.tenant_id,
            name=location.name,
            address=location.address,
            city=location.city,
            country=location.country,
            latitude=location.latitude,
            longitude=location.longitude,
            timezone=location.timezone,
            is_active=location.is_active,
            created_at=location.created_at,
            updated_at=location.updated_at,
            cameras_count=cameras_count or 0,
        )
        response.append(location_data)
    
    return response


@router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    location: LocationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new location."""
    # Verify tenant exists
    tenant = await db.get(Tenant, location.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check location limit
    locations_count = await db.scalar(
        select(func.count(Location.id)).where(Location.tenant_id == location.tenant_id)
    )
    if locations_count >= tenant.max_locations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant has reached maximum locations limit ({tenant.max_locations})"
        )
    
    db_location = Location(
        tenant_id=location.tenant_id,
        name=location.name,
        address=location.address,
        city=location.city,
        country=location.country,
        latitude=location.latitude,
        longitude=location.longitude,
        timezone=location.timezone,
    )
    db.add(db_location)
    await db.commit()
    await db.refresh(db_location)
    
    return LocationResponse(
        id=db_location.id,
        tenant_id=db_location.tenant_id,
        name=db_location.name,
        address=db_location.address,
        city=db_location.city,
        country=db_location.country,
        latitude=db_location.latitude,
        longitude=db_location.longitude,
        timezone=db_location.timezone,
        is_active=db_location.is_active,
        created_at=db_location.created_at,
        updated_at=db_location.updated_at,
        cameras_count=0,
    )


@router.get("/{location_id}", response_model=LocationWithCameras)
async def get_location(
    location_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific location with its cameras."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    # Get cameras
    result = await db.execute(
        select(Camera).where(Camera.location_id == location_id)
    )
    cameras = result.scalars().all()
    
    cameras_list = [
        {
            "id": cam.id,
            "name": cam.name,
            "rtsp_url": cam.rtsp_url,
            "is_active": cam.is_active,
            "stream_mode": cam.stream_mode,
        }
        for cam in cameras
    ]
    
    return LocationWithCameras(
        id=location.id,
        tenant_id=location.tenant_id,
        name=location.name,
        address=location.address,
        city=location.city,
        country=location.country,
        latitude=location.latitude,
        longitude=location.longitude,
        timezone=location.timezone,
        is_active=location.is_active,
        created_at=location.created_at,
        updated_at=location.updated_at,
        cameras_count=len(cameras_list),
        cameras=cameras_list,
    )


@router.patch("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: int,
    location_update: LocationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a location."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    update_data = location_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(location, key, value)
    
    await db.commit()
    await db.refresh(location)
    
    # Get cameras count
    cameras_count = await db.scalar(
        select(func.count(Camera.id)).where(Camera.location_id == location.id)
    )
    
    return LocationResponse(
        id=location.id,
        tenant_id=location.tenant_id,
        name=location.name,
        address=location.address,
        city=location.city,
        country=location.country,
        latitude=location.latitude,
        longitude=location.longitude,
        timezone=location.timezone,
        is_active=location.is_active,
        created_at=location.created_at,
        updated_at=location.updated_at,
        cameras_count=cameras_count or 0,
    )


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a location."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    # Check if location has cameras
    cameras_count = await db.scalar(
        select(func.count(Camera.id)).where(Camera.location_id == location_id)
    )
    if cameras_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete location with {cameras_count} cameras. Move or delete cameras first."
        )
    
    await db.delete(location)
    await db.commit()


# =============================================================================
# User-Location Assignment Routes
# =============================================================================

@router.get("/{location_id}/users")
async def list_location_users(
    location_id: int,
    db: AsyncSession = Depends(get_db)
):
    """List all users with access to this location."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    # Get users with all_locations_access or specific access to this location
    result = await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == location.tenant_id,
            TenantUser.all_locations_access == True
        )
    )
    all_access_users = result.scalars().all()
    
    # Get users with specific access
    result = await db.execute(
        select(TenantUser)
        .join(user_locations)
        .where(user_locations.c.location_id == location_id)
    )
    specific_users = result.scalars().all()
    
    # Combine and deduplicate
    users_dict = {u.id: u for u in all_access_users}
    users_dict.update({u.id: u for u in specific_users})
    
    return [
        {
            "id": u.id,
            "role": u.role,
            "all_locations_access": u.all_locations_access,
            "is_active": u.is_active,
        }
        for u in users_dict.values()
    ]


@router.post("/{location_id}/users/{user_id}", status_code=status.HTTP_201_CREATED)
async def assign_user_to_location(
    location_id: int,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Assign a user to a specific location."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    user = await db.scalar(
        select(TenantUser).where(
            TenantUser.id == user_id,
            TenantUser.tenant_id == location.tenant_id
        )
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this tenant"
        )
    
    # Check if already assigned
    result = await db.execute(
        select(user_locations).where(
            user_locations.c.user_id == user_id,
            user_locations.c.location_id == location_id
        )
    )
    if result.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already assigned to this location"
        )
    
    # Insert assignment
    await db.execute(
        user_locations.insert().values(user_id=user_id, location_id=location_id)
    )
    await db.commit()
    
    return {"message": "User assigned to location successfully"}


@router.delete("/{location_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_location(
    location_id: int,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Remove a user's access to a specific location."""
    await db.execute(
        user_locations.delete().where(
            user_locations.c.user_id == user_id,
            user_locations.c.location_id == location_id
        )
    )
    await db.commit()


# =============================================================================
# Move cameras between locations
# =============================================================================

@router.post("/{location_id}/cameras/{camera_id}")
async def assign_camera_to_location(
    location_id: int,
    camera_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Assign or move a camera to this location."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    camera = await db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
    
    # Ensure camera belongs to same tenant
    if camera.tenant_id and camera.tenant_id != location.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera belongs to a different tenant"
        )
    
    # Update camera's location and tenant
    camera.location_id = location_id
    camera.tenant_id = location.tenant_id
    
    await db.commit()
    await db.refresh(camera)
    
    return {
        "id": camera.id,
        "name": camera.name,
        "location_id": camera.location_id,
        "tenant_id": camera.tenant_id,
    }
