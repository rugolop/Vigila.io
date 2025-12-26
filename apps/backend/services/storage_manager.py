"""
Vigila.io - Storage Manager Service

Handles:
1. Retention policy enforcement (delete old recordings)
2. Space management (ensure disk doesn't fill up)
3. Automatic retention adjustment based on available space
4. Background cleanup tasks
"""
import os
import asyncio
import logging
import shutil
from datetime import datetime, timedelta
from glob import glob
from typing import Optional, Tuple, List, Dict
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import get_db, async_session_maker
from models import StorageVolume, StorageStatus, Camera, Tenant, Location

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Minimum free space threshold (5% or 1GB, whichever is larger)
MIN_FREE_PERCENT = 5.0
MIN_FREE_BYTES = 1 * 1024 * 1024 * 1024  # 1 GB

# Warning threshold (10% free)
WARNING_FREE_PERCENT = 10.0

# Cleanup check interval (every 5 minutes)
CLEANUP_INTERVAL_SECONDS = 5 * 60

# Minimum retention days allowed
MIN_RETENTION_DAYS = 1

# Average recording size per camera per day (estimate for calculations)
# ~500MB per hour * 24 hours = ~12GB per camera per day
ESTIMATED_GB_PER_CAMERA_PER_DAY = 12


# =============================================================================
# Storage Analysis Functions
# =============================================================================

def get_disk_usage(path: str) -> Tuple[int, int, int]:
    """Get disk usage for a path. Returns (total, used, free) in bytes."""
    try:
        if os.path.exists(path):
            usage = shutil.disk_usage(path)
            return usage.total, usage.used, usage.free
    except Exception as e:
        logger.error(f"Error getting disk usage for {path}: {e}")
    return 0, 0, 0


def get_recording_files(base_path: str) -> List[Dict]:
    """
    Get all recording files with their metadata.
    Returns list of dicts with: path, size, mtime, age_days
    """
    recordings = []
    
    if not os.path.exists(base_path):
        return recordings
    
    now = datetime.now()
    
    # Scan for MP4 files in all subdirectories
    # Structure: recordings/tenant/location/camera/*.mp4
    for mp4_file in glob(os.path.join(base_path, "**", "*.mp4"), recursive=True):
        try:
            stat = os.stat(mp4_file)
            mtime = datetime.fromtimestamp(stat.st_mtime)
            age_days = (now - mtime).days
            
            recordings.append({
                "path": mp4_file,
                "size": stat.st_size,
                "mtime": mtime,
                "age_days": age_days
            })
        except Exception as e:
            logger.debug(f"Error reading file {mp4_file}: {e}")
    
    return recordings


def get_recordings_by_age(base_path: str) -> Dict[int, List[Dict]]:
    """
    Group recordings by age in days.
    Returns dict: {age_days: [recording_info, ...]}
    """
    recordings = get_recording_files(base_path)
    by_age = {}
    
    for rec in recordings:
        age = rec["age_days"]
        if age not in by_age:
            by_age[age] = []
        by_age[age].append(rec)
    
    return by_age


def calculate_storage_by_age(base_path: str) -> List[Dict]:
    """
    Calculate storage used per day.
    Returns list of dicts with: age_days, size_bytes, file_count
    """
    by_age = get_recordings_by_age(base_path)
    result = []
    
    for age_days in sorted(by_age.keys()):
        files = by_age[age_days]
        result.append({
            "age_days": age_days,
            "size_bytes": sum(f["size"] for f in files),
            "file_count": len(files)
        })
    
    return result


def estimate_required_space(
    camera_count: int,
    retention_days: int,
    gb_per_camera_per_day: float = ESTIMATED_GB_PER_CAMERA_PER_DAY
) -> int:
    """
    Estimate required storage space in bytes.
    """
    gb_needed = camera_count * retention_days * gb_per_camera_per_day
    return int(gb_needed * 1024 * 1024 * 1024)


def calculate_max_retention_days(
    available_bytes: int,
    camera_count: int,
    gb_per_camera_per_day: float = ESTIMATED_GB_PER_CAMERA_PER_DAY
) -> int:
    """
    Calculate maximum retention days based on available space.
    """
    if camera_count <= 0 or gb_per_camera_per_day <= 0:
        return 365  # Default max if no cameras
    
    gb_available = available_bytes / (1024 * 1024 * 1024)
    max_days = int(gb_available / (camera_count * gb_per_camera_per_day))
    
    return max(MIN_RETENTION_DAYS, min(max_days, 365))


# =============================================================================
# Cleanup Functions
# =============================================================================

def delete_old_recordings(base_path: str, retention_days: int) -> Tuple[int, int]:
    """
    Delete recordings older than retention_days.
    Returns (files_deleted, bytes_freed).
    """
    deleted_count = 0
    bytes_freed = 0
    
    recordings = get_recording_files(base_path)
    
    for rec in recordings:
        if rec["age_days"] >= retention_days:
            try:
                os.remove(rec["path"])
                deleted_count += 1
                bytes_freed += rec["size"]
                logger.info(f"Deleted old recording: {rec['path']} (age: {rec['age_days']} days)")
            except Exception as e:
                logger.error(f"Error deleting {rec['path']}: {e}")
    
    # Cleanup empty directories
    cleanup_empty_directories(base_path)
    
    return deleted_count, bytes_freed


def delete_oldest_recordings_until_space(
    base_path: str,
    required_free_bytes: int,
    current_free_bytes: int
) -> Tuple[int, int]:
    """
    Delete oldest recordings until we have required_free_bytes available.
    Returns (files_deleted, bytes_freed).
    """
    if current_free_bytes >= required_free_bytes:
        return 0, 0
    
    bytes_to_free = required_free_bytes - current_free_bytes
    recordings = get_recording_files(base_path)
    
    # Sort by age (oldest first)
    recordings.sort(key=lambda x: x["mtime"])
    
    deleted_count = 0
    bytes_freed = 0
    
    for rec in recordings:
        if bytes_freed >= bytes_to_free:
            break
        
        try:
            os.remove(rec["path"])
            deleted_count += 1
            bytes_freed += rec["size"]
            logger.warning(f"Emergency cleanup: Deleted {rec['path']} to free space")
        except Exception as e:
            logger.error(f"Error deleting {rec['path']}: {e}")
    
    cleanup_empty_directories(base_path)
    
    return deleted_count, bytes_freed


def cleanup_empty_directories(base_path: str):
    """Remove empty directories in the recordings folder."""
    if not os.path.exists(base_path):
        return
    
    # Walk bottom-up to delete empty dirs
    for root, dirs, files in os.walk(base_path, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    logger.debug(f"Removed empty directory: {dir_path}")
            except Exception as e:
                logger.debug(f"Could not remove directory {dir_path}: {e}")


# =============================================================================
# Storage Analysis & Recommendation
# =============================================================================

async def analyze_storage_and_retention(
    db: AsyncSession,
    volume_id: Optional[int] = None
) -> Dict:
    """
    Analyze storage and provide retention recommendations.
    
    Returns:
    - current_status: Current storage status
    - recommended_retention: Recommended retention days
    - warning: Warning message if space is low
    - can_increase_retention: Whether retention can be increased
    """
    # Get storage volume
    if volume_id:
        result = await db.execute(
            select(StorageVolume).filter(StorageVolume.id == volume_id)
        )
    else:
        result = await db.execute(
            select(StorageVolume).filter(StorageVolume.is_primary == True)
        )
    
    volume = result.scalars().first()
    
    if not volume:
        return {
            "error": "No storage volume configured",
            "recommended_retention": 7
        }
    
    mount_path = volume.mount_path
    if not mount_path or not os.path.exists(mount_path):
        return {
            "error": f"Storage path not accessible: {mount_path}",
            "recommended_retention": 7
        }
    
    # Get disk usage
    total, used, free = get_disk_usage(mount_path)
    
    if total == 0:
        return {
            "error": "Cannot read disk space",
            "recommended_retention": 7
        }
    
    # Get camera count
    camera_result = await db.execute(
        select(Camera).filter(Camera.is_active == True)
    )
    cameras = camera_result.scalars().all()
    camera_count = len(cameras)
    
    # Calculate current usage
    usage_percent = (used / total) * 100
    free_percent = (free / total) * 100
    
    # Get recording statistics
    storage_by_age = calculate_storage_by_age(mount_path)
    total_recording_bytes = sum(s["size_bytes"] for s in storage_by_age)
    oldest_recording_days = max((s["age_days"] for s in storage_by_age), default=0)
    
    # Calculate actual average per day
    if storage_by_age and oldest_recording_days > 0:
        actual_gb_per_day = (total_recording_bytes / (1024**3)) / max(oldest_recording_days, 1)
        gb_per_camera_per_day = actual_gb_per_day / max(camera_count, 1)
    else:
        gb_per_camera_per_day = ESTIMATED_GB_PER_CAMERA_PER_DAY
    
    # Calculate recommended retention based on available space
    # Reserve MIN_FREE_PERCENT for safety
    usable_space = total * (1 - MIN_FREE_PERCENT / 100)
    recommended_retention = calculate_max_retention_days(
        usable_space, camera_count, gb_per_camera_per_day
    )
    
    # Check if current retention is sustainable
    current_retention = volume.retention_days or 7
    required_space = estimate_required_space(
        camera_count, current_retention, gb_per_camera_per_day
    )
    
    # Build response
    response = {
        "volume_id": volume.id,
        "volume_name": volume.name,
        "mount_path": mount_path,
        "current_retention_days": current_retention,
        "recommended_retention_days": recommended_retention,
        "storage": {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "usage_percent": round(usage_percent, 2),
            "free_percent": round(free_percent, 2),
        },
        "recordings": {
            "total_bytes": total_recording_bytes,
            "oldest_days": oldest_recording_days,
            "days_breakdown": storage_by_age[:10],  # First 10 days
        },
        "cameras": {
            "active_count": camera_count,
            "estimated_gb_per_camera_per_day": round(gb_per_camera_per_day, 2),
        },
        "warnings": [],
        "can_increase_retention": recommended_retention > current_retention,
    }
    
    # Add warnings
    if free_percent < MIN_FREE_PERCENT:
        response["warnings"].append({
            "level": "critical",
            "message": f"¡Espacio crítico! Solo {free_percent:.1f}% libre. Se eliminarán grabaciones automáticamente."
        })
    elif free_percent < WARNING_FREE_PERCENT:
        response["warnings"].append({
            "level": "warning",
            "message": f"Espacio bajo: {free_percent:.1f}% libre. Considera reducir la retención."
        })
    
    if current_retention > recommended_retention:
        response["warnings"].append({
            "level": "warning",
            "message": f"La retención actual ({current_retention} días) es mayor que la recomendada ({recommended_retention} días). "
                      f"El sistema ajustará automáticamente si es necesario."
        })
    
    if required_space > total:
        response["warnings"].append({
            "level": "error",
            "message": f"El espacio requerido ({required_space / (1024**3):.1f} GB) excede el total disponible."
        })
    
    return response


# =============================================================================
# Update Retention Settings
# =============================================================================

async def update_retention_settings(
    db: AsyncSession,
    volume_id: int,
    retention_days: int,
    auto_adjust: bool = True
) -> Dict:
    """
    Update retention settings for a storage volume.
    
    Args:
        db: Database session
        volume_id: Storage volume ID
        retention_days: Desired retention days
        auto_adjust: If True, automatically adjust to max possible if requested is too high
    
    Returns:
        Result with actual retention set and any warnings
    """
    # Get volume
    result = await db.execute(
        select(StorageVolume).filter(StorageVolume.id == volume_id)
    )
    volume = result.scalars().first()
    
    if not volume:
        return {"error": "Storage volume not found"}
    
    # Analyze storage
    analysis = await analyze_storage_and_retention(db, volume_id)
    
    if "error" in analysis:
        return analysis
    
    recommended = analysis["recommended_retention_days"]
    final_retention = retention_days
    warning = None
    
    # Check if requested retention is feasible
    if retention_days > recommended:
        if auto_adjust:
            final_retention = recommended
            warning = (
                f"La retención solicitada ({retention_days} días) no es posible con el espacio disponible. "
                f"Se ha ajustado automáticamente a {recommended} días."
            )
        else:
            return {
                "error": f"No hay espacio suficiente para {retention_days} días de retención. "
                        f"Máximo posible: {recommended} días.",
                "max_retention_days": recommended
            }
    
    # Enforce minimum
    if final_retention < MIN_RETENTION_DAYS:
        final_retention = MIN_RETENTION_DAYS
    
    # Update volume
    volume.retention_days = final_retention
    await db.commit()
    
    # Trigger cleanup of old recordings
    mount_path = volume.mount_path
    if mount_path and os.path.exists(mount_path):
        deleted, freed = delete_old_recordings(mount_path, final_retention)
        logger.info(f"Retention update cleanup: deleted {deleted} files, freed {freed / (1024**3):.2f} GB")
    
    return {
        "success": True,
        "volume_id": volume_id,
        "retention_days": final_retention,
        "warning": warning,
        "recommended_retention_days": recommended,
    }


# =============================================================================
# Background Cleanup Task
# =============================================================================

class StorageCleanupManager:
    """
    Background task manager for storage cleanup.
    """
    
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.last_cleanup: Optional[datetime] = None
        self.cleanup_stats = {
            "files_deleted": 0,
            "bytes_freed": 0,
            "last_run": None,
            "errors": []
        }
    
    async def start(self):
        """Start the background cleanup task."""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._cleanup_loop())
        logger.info("Storage cleanup manager started")
    
    async def stop(self):
        """Stop the background cleanup task."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Storage cleanup manager stopped")
    
    async def _cleanup_loop(self):
        """Main cleanup loop."""
        while self.running:
            try:
                await self._run_cleanup()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                self.cleanup_stats["errors"].append({
                    "time": datetime.now().isoformat(),
                    "error": str(e)
                })
            
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
    
    async def _run_cleanup(self):
        """Run a single cleanup cycle."""
        async with async_session_maker() as db:
            # Get all storage volumes
            result = await db.execute(
                select(StorageVolume).filter(StorageVolume.is_active == True)
            )
            volumes = result.scalars().all()
            
            total_deleted = 0
            total_freed = 0
            
            for volume in volumes:
                if not volume.mount_path or not os.path.exists(volume.mount_path):
                    continue
                
                mount_path = volume.mount_path
                retention_days = volume.retention_days or 7
                
                # Step 1: Delete recordings older than retention
                deleted, freed = delete_old_recordings(mount_path, retention_days)
                total_deleted += deleted
                total_freed += freed
                
                # Step 2: Check if we need emergency cleanup
                total, used, free = get_disk_usage(mount_path)
                
                if total > 0:
                    free_percent = (free / total) * 100
                    
                    if free_percent < MIN_FREE_PERCENT:
                        # Emergency: delete oldest until we have enough space
                        min_free = max(
                            total * MIN_FREE_PERCENT / 100,
                            MIN_FREE_BYTES
                        )
                        
                        emergency_deleted, emergency_freed = delete_oldest_recordings_until_space(
                            mount_path, min_free, free
                        )
                        
                        total_deleted += emergency_deleted
                        total_freed += emergency_freed
                        
                        if emergency_deleted > 0:
                            logger.warning(
                                f"Emergency cleanup on {volume.name}: "
                                f"deleted {emergency_deleted} files, freed {emergency_freed / (1024**3):.2f} GB"
                            )
                    
                    # Update volume status
                    new_total, new_used, new_free = get_disk_usage(mount_path)
                    new_free_percent = (new_free / new_total) * 100 if new_total > 0 else 0
                    
                    if new_free_percent < MIN_FREE_PERCENT:
                        volume.status = StorageStatus.FULL.value
                    else:
                        volume.status = StorageStatus.ACTIVE.value
                    
                    volume.total_bytes = new_total
                    volume.used_bytes = new_used
                    volume.last_checked = datetime.utcnow()
            
            await db.commit()
            
            # Update stats
            self.last_cleanup = datetime.now()
            self.cleanup_stats["files_deleted"] += total_deleted
            self.cleanup_stats["bytes_freed"] += total_freed
            self.cleanup_stats["last_run"] = self.last_cleanup.isoformat()
            
            if total_deleted > 0:
                logger.info(
                    f"Cleanup complete: {total_deleted} files deleted, "
                    f"{total_freed / (1024**3):.2f} GB freed"
                )
    
    async def force_cleanup(self) -> Dict:
        """Force an immediate cleanup cycle."""
        await self._run_cleanup()
        return {
            "success": True,
            "stats": self.cleanup_stats.copy()
        }
    
    def get_status(self) -> Dict:
        """Get cleanup manager status."""
        return {
            "running": self.running,
            "last_cleanup": self.last_cleanup.isoformat() if self.last_cleanup else None,
            "stats": self.cleanup_stats.copy()
        }


# Global instance
cleanup_manager = StorageCleanupManager()


# =============================================================================
# Startup/Shutdown Functions
# =============================================================================

async def start_storage_manager():
    """Start the storage manager on application startup."""
    await cleanup_manager.start()


async def stop_storage_manager():
    """Stop the storage manager on application shutdown."""
    await cleanup_manager.stop()
