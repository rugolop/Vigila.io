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
from models import RecordingLog, Camera
from schemas import RecordingLogResponse
from pydantic import BaseModel

router = APIRouter(
    prefix="/recordings",
    tags=["recordings"],
)


class RecordingSearchParams(BaseModel):
    camera_id: Optional[int] = None  # None = all cameras
    date: Optional[str] = None       # YYYY-MM-DD format
    start_time: Optional[str] = None # HH:MM format
    end_time: Optional[str] = None   # HH:MM format
    page: int = 1
    page_size: int = 50


class RecordingInfo(BaseModel):
    id: str
    camera_id: int
    camera_name: str
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


@router.get("/cameras-with-recordings")
async def get_cameras_with_recordings(db: AsyncSession = Depends(get_db)):
    """Get list of cameras that have recordings available."""
    base_path = "/recordings"
    cameras_with_recordings = []
    
    # Get all cameras from database
    result = await db.execute(select(Camera))
    cameras = {sanitize_name(c.name): c for c in result.scalars().all()}
    
    # Check which folders exist in recordings
    if os.path.exists(base_path):
        for folder_name in os.listdir(base_path):
            folder_path = os.path.join(base_path, folder_name)
            if os.path.isdir(folder_path):
                # Check if has any recordings
                recordings = glob(os.path.join(folder_path, "*.mp4"))
                if recordings:
                    # Find matching camera
                    camera = cameras.get(folder_name)
                    cameras_with_recordings.append({
                        "folder_name": folder_name,
                        "camera_id": camera.id if camera else None,
                        "camera_name": camera.name if camera else folder_name,
                        "recording_count": len(recordings)
                    })
    
    return cameras_with_recordings


def sanitize_name(name: str) -> str:
    """Convert camera name to folder-safe format (matches MediaMTX path names)."""
    return name.lower().replace(" ", "_").replace("-", "_")


def parse_recording_id(recording_id: str) -> tuple[str, str]:
    """
    Parse recording ID to extract folder_name and filename.
    ID format: {folder_name}::{filename}
    """
    if "::" not in recording_id:
        raise ValueError("Invalid recording ID format. Expected 'folder_name::filename'")
    
    parts = recording_id.split("::", 1)
    return parts[0], parts[1]


@router.post("/search", response_model=PaginatedRecordings)
async def search_recordings(
    params: RecordingSearchParams, 
    db: AsyncSession = Depends(get_db)
):
    """
    Search recordings with filters and pagination.
    
    - camera_id: Filter by specific camera (optional, None = all cameras)
    - date: Filter by date in YYYY-MM-DD format (optional)
    - start_time: Filter recordings after this time HH:MM (optional)
    - end_time: Filter recordings before this time HH:MM (optional)
    - page: Page number (1-indexed)
    - page_size: Number of results per page
    """
    base_path = "/recordings"
    all_results: List[RecordingInfo] = []
    
    # Get cameras from database for name mapping
    result = await db.execute(select(Camera))
    cameras = {sanitize_name(c.name): c for c in result.scalars().all()}
    
    # Determine which folders to search
    folders_to_search = []
    if params.camera_id:
        # Find specific camera
        camera_result = await db.execute(select(Camera).filter(Camera.id == params.camera_id))
        camera = camera_result.scalars().first()
        if camera:
            folder_name = sanitize_name(camera.name)
            folders_to_search.append((folder_name, camera))
    else:
        # Search all folders
        if os.path.exists(base_path):
            for folder_name in os.listdir(base_path):
                if os.path.isdir(os.path.join(base_path, folder_name)):
                    camera = cameras.get(folder_name)
                    folders_to_search.append((folder_name, camera))
    
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
    
    # Search recordings
    for folder_name, camera in folders_to_search:
        folder_path = os.path.join(base_path, folder_name)
        if not os.path.exists(folder_path):
            continue
        
        for filepath in glob(os.path.join(folder_path, "*.mp4")):
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
            
            # Create result entry with new ID format using :: separator
            all_results.append(RecordingInfo(
                id=f"{folder_name}::{filename}",
                camera_id=camera.id if camera else 0,
                camera_name=camera.name if camera else folder_name,
                folder_name=folder_name,
                filename=filename,
                start_time=recording_time,
                duration_seconds=duration,
                file_size_mb=round(file_size_mb, 2),
                file_path=f"http://localhost:8001/media/{folder_name}/{filename}"
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
    
    folder_name = sanitize_name(camera.name)
    folder_path = os.path.join("/recordings", folder_name)
    
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
    """Delete a recording file. ID format: folder_name::filename"""
    try:
        folder_name, filename = parse_recording_id(recording_id)
        file_path = os.path.join("/recordings", folder_name, filename)
        
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
    """Delete multiple recordings at once. IDs format: folder_name::filename"""
    deleted = []
    errors = []
    
    for recording_id in recording_ids:
        try:
            folder_name, filename = parse_recording_id(recording_id)
            file_path = os.path.join("/recordings", folder_name, filename)
            
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


@router.get("/download/{folder_name}/{filename}")
async def download_recording(folder_name: str, filename: str):
    """Download a single recording file as compressed zip."""
    file_path = os.path.join("/recordings", folder_name, filename)
    
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
                folder_name, filename = parse_recording_id(recording_id)
                file_path = os.path.join("/recordings", folder_name, filename)
                
                if os.path.exists(file_path):
                    # Add to zip with folder structure
                    archive_name = f"{folder_name}/{filename}"
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
