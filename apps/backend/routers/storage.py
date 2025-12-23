"""
Storage Volume Management Router

Handles CRUD operations for storage volumes and provides storage statistics.
Supports multiple storage types: local, NAS (SMB/NFS), USB, and cloud (S3/Azure/GCS).
"""

import os
import shutil
import json
from datetime import datetime
from typing import List, Optional
from glob import glob

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import get_db
from models import StorageVolume, StorageType, StorageStatus
from schemas import (
    StorageVolumeCreate,
    StorageVolumeUpdate,
    StorageVolumeResponse,
    StorageStats,
    StorageOverview,
)


router = APIRouter(
    prefix="/storage",
    tags=["storage"],
)


# ============================================================================
# Helper Functions
# ============================================================================

def get_disk_usage(path: str) -> tuple[int, int, int]:
    """Get disk usage for a path. Returns (total, used, free) in bytes."""
    try:
        if os.path.exists(path):
            usage = shutil.disk_usage(path)
            return usage.total, usage.used, usage.free
    except Exception as e:
        print(f"Error getting disk usage for {path}: {e}")
    return 0, 0, 0


def count_recordings_in_path(path: str) -> tuple[int, Optional[datetime], Optional[datetime]]:
    """Count recordings and find oldest/newest. Returns (count, oldest, newest)."""
    if not os.path.exists(path):
        return 0, None, None
    
    recordings = []
    for camera_dir in glob(os.path.join(path, "*")):
        if os.path.isdir(camera_dir):
            recordings.extend(glob(os.path.join(camera_dir, "*.mp4")))
    
    if not recordings:
        return 0, None, None
    
    # Get modification times
    times = []
    for rec in recordings:
        try:
            mtime = os.path.getmtime(rec)
            times.append(datetime.fromtimestamp(mtime))
        except:
            pass
    
    if times:
        return len(recordings), min(times), max(times)
    return len(recordings), None, None


def get_storage_stats(mount_path: str) -> StorageStats:
    """Get detailed storage statistics for a volume."""
    total, used, free = get_disk_usage(mount_path)
    count, oldest, newest = count_recordings_in_path(mount_path)
    
    usage_percent = (used / total * 100) if total > 0 else 0
    
    return StorageStats(
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
        usage_percent=round(usage_percent, 2),
        recording_count=count,
        oldest_recording=oldest,
        newest_recording=newest,
    )


async def update_volume_status(db: AsyncSession, volume_id: int, status: str, 
                                total: int = None, used: int = None):
    """Update volume status and metrics in database."""
    update_data = {
        "status": status,
        "last_checked": datetime.utcnow(),
    }
    if total is not None:
        update_data["total_bytes"] = total
    if used is not None:
        update_data["used_bytes"] = used
    
    await db.execute(
        update(StorageVolume)
        .where(StorageVolume.id == volume_id)
        .values(**update_data)
    )
    await db.commit()


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=List[StorageVolumeResponse])
async def list_storage_volumes(db: AsyncSession = Depends(get_db)):
    """Get all configured storage volumes."""
    result = await db.execute(select(StorageVolume).order_by(StorageVolume.created_at))
    volumes = result.scalars().all()
    return volumes


@router.get("/overview", response_model=StorageOverview)
async def get_storage_overview(db: AsyncSession = Depends(get_db)):
    """Get overview of all storage with aggregated statistics."""
    result = await db.execute(select(StorageVolume))
    volumes = result.scalars().all()
    
    total_storage = 0
    total_used = 0
    total_free = 0
    total_recordings = 0
    primary_id = None
    
    volume_responses = []
    for vol in volumes:
        if vol.mount_path and os.path.exists(vol.mount_path):
            t, u, f = get_disk_usage(vol.mount_path)
            count, _, _ = count_recordings_in_path(vol.mount_path)
            total_storage += t
            total_used += u
            total_free += f
            total_recordings += count
            
            # Update in DB
            vol.total_bytes = t
            vol.used_bytes = u
            vol.status = StorageStatus.ACTIVE.value if vol.is_active else StorageStatus.INACTIVE.value
        else:
            vol.status = StorageStatus.ERROR.value
        
        if vol.is_primary:
            primary_id = vol.id
        
        volume_responses.append(vol)
    
    await db.commit()
    
    return StorageOverview(
        volumes=volume_responses,
        total_storage_bytes=total_storage,
        total_used_bytes=total_used,
        total_free_bytes=total_free,
        total_recordings=total_recordings,
        primary_volume_id=primary_id,
    )


@router.get("/{volume_id}", response_model=StorageVolumeResponse)
async def get_storage_volume(volume_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific storage volume by ID."""
    result = await db.execute(select(StorageVolume).filter(StorageVolume.id == volume_id))
    volume = result.scalars().first()
    if not volume:
        raise HTTPException(status_code=404, detail="Storage volume not found")
    return volume


@router.get("/{volume_id}/stats", response_model=StorageStats)
async def get_volume_stats(volume_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed statistics for a storage volume."""
    result = await db.execute(select(StorageVolume).filter(StorageVolume.id == volume_id))
    volume = result.scalars().first()
    if not volume:
        raise HTTPException(status_code=404, detail="Storage volume not found")
    
    if not volume.mount_path or not os.path.exists(volume.mount_path):
        raise HTTPException(status_code=400, detail="Volume mount path not accessible")
    
    return get_storage_stats(volume.mount_path)


@router.post("/", response_model=StorageVolumeResponse)
async def create_storage_volume(
    volume: StorageVolumeCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new storage volume configuration.
    
    Storage Types:
    - **local**: Local directory on the host machine
    - **nas_smb**: Network Attached Storage via SMB/CIFS protocol
    - **nas_nfs**: Network Attached Storage via NFS protocol
    - **usb**: External USB drive
    - **s3**: Amazon S3 or compatible storage (MinIO, etc.)
    - **azure**: Azure Blob Storage
    - **gcs**: Google Cloud Storage
    """
    # Check if name already exists
    existing = await db.execute(
        select(StorageVolume).filter(StorageVolume.name == volume.name)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Volume name already exists")
    
    # Generate mount path if not provided
    mount_path = volume.mount_path
    if not mount_path:
        safe_name = volume.name.lower().replace(" ", "_")
        mount_path = f"/recordings/{safe_name}"
    
    # If setting as primary, unset other primaries
    if volume.is_primary:
        await db.execute(
            update(StorageVolume)
            .where(StorageVolume.is_primary == True)
            .values(is_primary=False)
        )
    
    # Create the volume
    db_volume = StorageVolume(
        name=volume.name,
        storage_type=volume.storage_type,
        mount_path=mount_path,
        is_primary=volume.is_primary,
        is_active=volume.is_active,
        status=StorageStatus.INACTIVE.value,
        host_path=volume.host_path,
        server_address=volume.server_address,
        share_name=volume.share_name,
        username=volume.username,
        password=volume.password,
        extra_options=volume.extra_options,
        retention_days=volume.retention_days,
    )
    
    db.add(db_volume)
    await db.commit()
    await db.refresh(db_volume)
    
    return db_volume


@router.put("/{volume_id}", response_model=StorageVolumeResponse)
async def update_storage_volume(
    volume_id: int,
    volume_update: StorageVolumeUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a storage volume configuration."""
    result = await db.execute(select(StorageVolume).filter(StorageVolume.id == volume_id))
    db_volume = result.scalars().first()
    if not db_volume:
        raise HTTPException(status_code=404, detail="Storage volume not found")
    
    # Check unique name if updating
    if volume_update.name and volume_update.name != db_volume.name:
        existing = await db.execute(
            select(StorageVolume).filter(StorageVolume.name == volume_update.name)
        )
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="Volume name already exists")
    
    # If setting as primary, unset other primaries
    if volume_update.is_primary:
        await db.execute(
            update(StorageVolume)
            .where(StorageVolume.is_primary == True)
            .where(StorageVolume.id != volume_id)
            .values(is_primary=False)
        )
    
    # Update fields
    update_data = volume_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_volume, key, value)
    
    await db.commit()
    await db.refresh(db_volume)
    return db_volume


@router.delete("/{volume_id}")
async def delete_storage_volume(volume_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a storage volume configuration."""
    result = await db.execute(select(StorageVolume).filter(StorageVolume.id == volume_id))
    db_volume = result.scalars().first()
    if not db_volume:
        raise HTTPException(status_code=404, detail="Storage volume not found")
    
    # Don't delete if it's the last/primary volume with recordings
    if db_volume.is_primary:
        count, _, _ = count_recordings_in_path(db_volume.mount_path or "")
        if count > 0:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete primary volume with existing recordings"
            )
    
    await db.delete(db_volume)
    await db.commit()
    return {"message": "Storage volume deleted"}


@router.post("/{volume_id}/check")
async def check_storage_volume(
    volume_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Check and update storage volume status and metrics.
    
    This endpoint verifies the volume is accessible and updates:
    - Connection status
    - Total/used space
    - Recording count
    """
    result = await db.execute(select(StorageVolume).filter(StorageVolume.id == volume_id))
    db_volume = result.scalars().first()
    if not db_volume:
        raise HTTPException(status_code=404, detail="Storage volume not found")
    
    path = db_volume.mount_path
    
    if not path:
        return {"status": "error", "message": "No mount path configured"}
    
    if os.path.exists(path):
        total, used, free = get_disk_usage(path)
        count, oldest, newest = count_recordings_in_path(path)
        
        # Check if nearly full (>95%)
        usage_percent = (used / total * 100) if total > 0 else 0
        status = StorageStatus.FULL.value if usage_percent > 95 else StorageStatus.ACTIVE.value
        
        await update_volume_status(db, volume_id, status, total, used)
        
        return {
            "status": status,
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "usage_percent": round(usage_percent, 2),
            "recording_count": count,
            "oldest_recording": oldest.isoformat() if oldest else None,
            "newest_recording": newest.isoformat() if newest else None,
        }
    else:
        await update_volume_status(db, volume_id, StorageStatus.ERROR.value)
        return {"status": "error", "message": f"Path not accessible: {path}"}


@router.post("/{volume_id}/set-primary")
async def set_primary_volume(volume_id: int, db: AsyncSession = Depends(get_db)):
    """Set a storage volume as the primary recording destination."""
    result = await db.execute(select(StorageVolume).filter(StorageVolume.id == volume_id))
    db_volume = result.scalars().first()
    if not db_volume:
        raise HTTPException(status_code=404, detail="Storage volume not found")
    
    # Verify volume is accessible
    if not db_volume.mount_path or not os.path.exists(db_volume.mount_path):
        raise HTTPException(status_code=400, detail="Volume not accessible")
    
    # Unset all primaries
    await db.execute(
        update(StorageVolume)
        .where(StorageVolume.is_primary == True)
        .values(is_primary=False)
    )
    
    # Set this one as primary
    db_volume.is_primary = True
    db_volume.is_active = True
    
    await db.commit()
    
    return {"message": f"Volume '{db_volume.name}' set as primary"}


@router.get("/types/info")
async def get_storage_types_info():
    """Get information about supported storage types and their configuration."""
    return {
        "types": [
            {
                "type": "local",
                "name": "Local",
                "description": "Directorio local en la máquina host",
                "fields": ["host_path"],
                "icon": "folder"
            },
            {
                "type": "nas_smb",
                "name": "NAS (SMB/CIFS)",
                "description": "Almacenamiento en red via protocolo SMB/CIFS (Windows sharing)",
                "fields": ["server_address", "share_name", "username", "password"],
                "icon": "server"
            },
            {
                "type": "nas_nfs",
                "name": "NAS (NFS)",
                "description": "Almacenamiento en red via protocolo NFS",
                "fields": ["server_address", "share_name"],
                "icon": "server"
            },
            {
                "type": "usb",
                "name": "USB",
                "description": "Disco externo USB",
                "fields": ["host_path"],
                "icon": "usb"
            },
            {
                "type": "s3",
                "name": "Amazon S3",
                "description": "Amazon S3 o compatible (MinIO, Wasabi, etc.)",
                "fields": ["server_address", "share_name", "username", "password"],
                "hint": "server_address=endpoint, share_name=bucket, username=access_key, password=secret_key",
                "icon": "cloud"
            },
            {
                "type": "azure",
                "name": "Azure Blob Storage",
                "description": "Microsoft Azure Blob Storage",
                "fields": ["share_name", "password"],
                "hint": "share_name=container, password=connection_string",
                "icon": "cloud"
            },
            {
                "type": "gcs",
                "name": "Google Cloud Storage",
                "description": "Google Cloud Storage",
                "fields": ["share_name", "extra_options"],
                "hint": "share_name=bucket, extra_options=service_account_json",
                "icon": "cloud"
            }
        ]
    }


# Initialize default storage on startup
async def initialize_default_storage(db: AsyncSession):
    """Create default local storage if no storage exists."""
    result = await db.execute(select(StorageVolume))
    existing = result.scalars().first()
    
    if not existing:
        default_volume = StorageVolume(
            name="Local Storage",
            storage_type=StorageType.LOCAL.value,
            mount_path="/recordings",
            host_path="./recordings",
            is_primary=True,
            is_active=True,
            status=StorageStatus.ACTIVE.value,
            retention_days=7,
        )
        db.add(default_volume)
        await db.commit()
        print("Created default local storage volume")
