from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime, time
import os
import io
import zipfile
from glob import glob
from pathlib import Path

from database import get_db
from models import RecordingLog, Camera, Tenant, Location
from schemas import RecordingLogResponse
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/recordings",
    tags=["recordings"],
)


class RecordingSearchParams(BaseModel):
    camera_id: Optional[int] = None  # None = all cameras
    tenant_id: Optional[int] = None  # Filter by tenant
    location_id: Optional[int] = None  # Filter by location
    date: Optional[str] = None       # YYYY-MM-DD format
    start_time: Optional[str] = None # HH:MM format
    end_time: Optional[str] = None   # HH:MM format
    page: int = 1
    page_size: int = 50


class RecordingInfo(BaseModel):
    id: str
    camera_id: int
    camera_name: str
    tenant_id: Optional[int] = None
    location_id: Optional[int] = None
    folder_name: str  # Added to help with file operations
    filename: str
    start_time: datetime
    duration_seconds: int
    file_size_mb: float
    file_path: str


class PaginatedRecordings(BaseModel):
    recordings: List[RecordingInfo]
    total: int
    page: int
    page_size: int
    total_pages: int


class BulkDownloadRequest(BaseModel):
    recording_ids: List[str]


def get_file_duration_estimate(file_size_bytes: int) -> int:
    """Estimate duration based on file size (rough estimate for 1080p ~60MB/min)"""
    mb = file_size_bytes / (1024 * 1024)
    # Approximately 1 MB per second for typical 1080p h264
    return int(mb)


def parse_recording_filename(filename: str) -> Optional[datetime]:
    """Parse MediaMTX recording filename format: YYYY-MM-DD_HH-MM-SS.mp4"""
    try:
        date_str = filename.replace(".mp4", "")
        return datetime.strptime(date_str, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        return None


def get_camera_recording_path(camera: Camera) -> str:
    """
    Get the recording path for a camera based on tenant/location structure.
    
    New structure: /recordings/tenant_{id}/location_{id}/camera_{id}
    Legacy structure: /recordings/{camera_name}
    
    Returns the path that exists, preferring new structure.
    """
    base_path = "/recordings"
    
    # New structure with tenant/location
    if camera.tenant_id and camera.location_id:
        new_path = os.path.join(
            base_path, 
            f"tenant_{camera.tenant_id}",
            f"location_{camera.location_id}",
            f"camera_{camera.id}"
        )
        if os.path.exists(new_path):
            return new_path
    
    # Try camera ID based path
    camera_id_path = os.path.join(base_path, f"camera_{camera.id}")
    if os.path.exists(camera_id_path):
        return camera_id_path
    
    # Legacy: camera name based path
    legacy_path = os.path.join(base_path, sanitize_name(camera.name))
    if os.path.exists(legacy_path):
        return legacy_path
    
    # Return new path as default for creation
    if camera.tenant_id and camera.location_id:
        return os.path.join(
            base_path,
            f"tenant_{camera.tenant_id}",
            f"location_{camera.location_id}",
            f"camera_{camera.id}"
        )
    
    # Fallback to camera name
    return os.path.join(base_path, sanitize_name(camera.name))


def ensure_recording_directory(camera: Camera) -> str:
    """Create and return the recording directory for a camera."""
    path = get_camera_recording_path(camera)
    os.makedirs(path, exist_ok=True)
    return path


@router.get("/cameras-with-recordings")
async def get_cameras_with_recordings(
    tenant_id: Optional[int] = Query(None, description="Filter by tenant ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get list of cameras that have recordings available."""
    base_path = "/recordings"
    cameras_with_recordings = []
    
    # Get all cameras from database with optional tenant filter
    query = select(Camera)
    if tenant_id:
        query = query.filter(Camera.tenant_id == tenant_id)
    result = await db.execute(query)
    cameras = result.scalars().all()
    
    # Build lookup for both new and legacy structures
    camera_by_name = {sanitize_name(c.name): c for c in cameras}
    camera_by_id = {c.id: c for c in cameras}
    
    processed_cameras = set()
    
    # Check new structure: /recordings/tenant_X/location_X/camera_X
    if os.path.exists(base_path):
        for tenant_folder in os.listdir(base_path):
            if tenant_folder.startswith("tenant_"):
                tenant_path = os.path.join(base_path, tenant_folder)
                if not os.path.isdir(tenant_path):
                    continue
                    
                for location_folder in os.listdir(tenant_path):
                    if location_folder.startswith("location_"):
                        location_path = os.path.join(tenant_path, location_folder)
                        if not os.path.isdir(location_path):
                            continue
                            
                        for camera_folder in os.listdir(location_path):
                            if camera_folder.startswith("camera_"):
                                camera_path = os.path.join(location_path, camera_folder)
                                if not os.path.isdir(camera_path):
                                    continue
                                
                                # Extract camera ID
                                try:
                                    cam_id = int(camera_folder.replace("camera_", ""))
                                except ValueError:
                                    continue
                                
                                camera = camera_by_id.get(cam_id)
                                if not camera:
                                    continue
                                
                                recordings = glob(os.path.join(camera_path, "*.mp4"))
                                if recordings:
                                    processed_cameras.add(camera.id)
                                    cameras_with_recordings.append({
                                        "folder_name": f"{tenant_folder}/{location_folder}/{camera_folder}",
                                        "camera_id": camera.id,
                                        "camera_name": camera.name,
                                        "tenant_id": camera.tenant_id,
                                        "location_id": camera.location_id,
                                        "recording_count": len(recordings)
                                    })
        
        # Check legacy structure: /recordings/{camera_name}
        for folder_name in os.listdir(base_path):
            folder_path = os.path.join(base_path, folder_name)
            if os.path.isdir(folder_path) and not folder_name.startswith(("tenant_", "camera_")):
                # Legacy folder with camera name
                camera = camera_by_name.get(folder_name)
                if camera and camera.id not in processed_cameras:
                    recordings = glob(os.path.join(folder_path, "*.mp4"))
                    if recordings:
                        cameras_with_recordings.append({
                            "folder_name": folder_name,
                            "camera_id": camera.id,
                            "camera_name": camera.name,
                            "tenant_id": camera.tenant_id,
                            "location_id": camera.location_id,
                            "recording_count": len(recordings)
                        })
    
    return cameras_with_recordings


def sanitize_name(name: str) -> str:
    """Convert camera name to folder-safe format (matches MediaMTX path names)."""
    return name.lower().replace(" ", "_").replace("-", "_")


def parse_recording_id(recording_id: str) -> tuple[str, str]:
    """
    Parse recording ID to extract folder_path and filename.
    ID format: {folder_path}::{filename}
    folder_path can contain subdirectories like tenant_1/location_1/camera_1
    """
    if "::" not in recording_id:
        raise ValueError("Invalid recording ID format. Expected 'folder_path::filename'")
    
    parts = recording_id.split("::", 1)
    return parts[0], parts[1]


def get_recording_file_path(folder_path: str, filename: str) -> str:
    """Get the full file path for a recording."""
    base_path = "/recordings"
    # Normalize path separators
    normalized_folder = folder_path.replace("/", os.sep).replace("\\", os.sep)
    return os.path.join(base_path, normalized_folder, filename)




@router.get("", response_model=List[RecordingInfo])
async def get_recordings(
    camera_id: Optional[int] = Query(None),
    tenant_id: Optional[int] = Query(None),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent recordings with optional filters.
    Returns up to `limit` most recent recordings.
    """
    # Use the same logic as search but simplified
    params = RecordingSearchParams(
        camera_id=camera_id,
        tenant_id=tenant_id,
        page=1,
        page_size=limit
    )
    
    # Call the search function to reuse logic
    result = await search_recordings(params, db)
    return result.recordings


@router.post("/search", response_model=PaginatedRecordings)
async def search_recordings(
    params: RecordingSearchParams, 
    db: AsyncSession = Depends(get_db)
):
    """
    Search recordings with filters and pagination.
    
    - camera_id: Filter by specific camera (optional, None = all cameras)
    - tenant_id: Filter by tenant (optional)
    - location_id: Filter by location (optional)
    - date: Filter by date in YYYY-MM-DD format (optional)
    - start_time: Filter recordings after this time HH:MM (optional)
    - end_time: Filter recordings before this time HH:MM (optional)
    - page: Page number (1-indexed)
    - page_size: Number of results per page
    """
    base_path = "/recordings"
    all_results: List[RecordingInfo] = []
    
    # Build camera query with filters
    query = select(Camera)
    if params.tenant_id:
        query = query.filter(Camera.tenant_id == params.tenant_id)
    if params.location_id:
        query = query.filter(Camera.location_id == params.location_id)
    if params.camera_id:
        query = query.filter(Camera.id == params.camera_id)
    
    result = await db.execute(query)
    cameras = result.scalars().all()
    
    # Parse date filter
    filter_date = None
    if params.date:
        try:
            filter_date = datetime.strptime(params.date, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    # Parse time filters
    filter_start_time = None
    filter_end_time = None
    if params.start_time:
        try:
            parts = params.start_time.split(":")
            filter_start_time = time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            pass
    if params.end_time:
        try:
            parts = params.end_time.split(":")
            filter_end_time = time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            pass
    
    # Search recordings for each camera
    for camera in cameras:
        recording_path = get_camera_recording_path(camera)
        
        if not os.path.exists(recording_path):
            continue
        
        for filepath in glob(os.path.join(recording_path, "*.mp4")):
            filename = os.path.basename(filepath)
            recording_time = parse_recording_filename(filename)
            
            if not recording_time:
                continue
            
            # Apply date filter
            if filter_date and recording_time.date() != filter_date:
                continue
            
            # Apply time filters
            rec_time = recording_time.time()
            if filter_start_time and rec_time < filter_start_time:
                continue
            if filter_end_time and rec_time > filter_end_time:
                continue
            
            # Get file info
            try:
                file_stat = os.stat(filepath)
                file_size_mb = file_stat.st_size / (1024 * 1024)
                duration = get_file_duration_estimate(file_stat.st_size)
            except OSError:
                file_size_mb = 0
                duration = 0
            
            # Get relative path from base for folder_name
            relative_path = os.path.relpath(recording_path, base_path)
            
            # Create result entry
            all_results.append(RecordingInfo(
                id=f"{relative_path}::{filename}",
                camera_id=camera.id,
                camera_name=camera.name,
                tenant_id=camera.tenant_id,
                location_id=camera.location_id,
                folder_name=relative_path,
                filename=filename,
                start_time=recording_time,
                duration_seconds=duration,
                file_size_mb=round(file_size_mb, 2),
                file_path=f"http://localhost:8001/media/{relative_path.replace(os.sep, '/')}/{filename}"
            ))
    
    # Sort by start_time descending (newest first)
    all_results.sort(key=lambda x: x.start_time, reverse=True)
    
    # Paginate results
    total = len(all_results)
    total_pages = (total + params.page_size - 1) // params.page_size
    start_idx = (params.page - 1) * params.page_size
    end_idx = start_idx + params.page_size
    paginated_results = all_results[start_idx:end_idx]
    
    return PaginatedRecordings(
        recordings=paginated_results,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages
    )


@router.get("/dates/{camera_id}")
async def get_available_dates(camera_id: int, db: AsyncSession = Depends(get_db)):
    """Get list of dates that have recordings for a camera."""
    # Get camera
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalars().first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    folder_path = get_camera_recording_path(camera)
    
    dates = set()
    if os.path.exists(folder_path):
        for filename in os.listdir(folder_path):
            if filename.endswith(".mp4"):
                recording_time = parse_recording_filename(filename)
                if recording_time:
                    dates.add(recording_time.date().isoformat())
    
    return sorted(list(dates), reverse=True)


@router.delete("/{recording_id:path}")
async def delete_recording(recording_id: str):
    """Delete a recording file. ID format: folder_path::filename"""
    try:
        folder_path, filename = parse_recording_id(recording_id)
        file_path = get_recording_file_path(folder_path, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Recording not found: {file_path}")
        
        os.remove(file_path)
        return {"success": True, "deleted": recording_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete-bulk")
async def delete_recordings_bulk(recording_ids: List[str]):
    """Delete multiple recordings at once. IDs format: folder_path::filename"""
    deleted = []
    errors = []
    
    for recording_id in recording_ids:
        try:
            folder_path, filename = parse_recording_id(recording_id)
            file_path = get_recording_file_path(folder_path, filename)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted.append(recording_id)
            else:
                errors.append({"id": recording_id, "error": "File not found"})
        except ValueError as e:
            errors.append({"id": recording_id, "error": str(e)})
        except Exception as e:
            errors.append({"id": recording_id, "error": str(e)})
    
    return {
        "deleted_count": len(deleted),
        "deleted": deleted,
        "errors": errors
    }


@router.get("/download/{folder_path:path}")
async def download_recording(folder_path: str):
    """Download a single recording file as compressed zip. Path includes filename."""
    # folder_path is something like "tenant_1/location_1/camera_1/filename.mp4"
    # or legacy "camera_name/filename.mp4"
    
    # Split the path to get folder and filename
    parts = folder_path.rsplit("/", 1)
    if len(parts) != 2 or not parts[1].endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Invalid path format")
    
    folder, filename = parts
    file_path = get_recording_file_path(folder, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Recording not found")
    
    # Create zip in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(file_path, filename)
    
    zip_buffer.seek(0)
    zip_filename = filename.replace(".mp4", ".zip")
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"'
        }
    )


@router.post("/download-bulk")
async def download_recordings_bulk(request: BulkDownloadRequest):
    """Download multiple recordings as a single compressed zip file."""
    if not request.recording_ids:
        raise HTTPException(status_code=400, detail="No recordings specified")
    
    # Create zip in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for recording_id in request.recording_ids:
            try:
                folder_path, filename = parse_recording_id(recording_id)
                file_path = get_recording_file_path(folder_path, filename)
                
                if os.path.exists(file_path):
                    # Add to zip with folder structure
                    archive_name = f"{folder_path.replace(os.sep, '/')}/{filename}"
                    zip_file.write(file_path, archive_name)
            except ValueError:
                continue  # Skip invalid IDs
    
    zip_buffer.seek(0)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"recordings_{timestamp}.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"'
        }
    )
