from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from typing import List, Optional
from pydantic import BaseModel

from database import get_db
from models import Camera, Location, Tenant
from schemas import CameraCreate, CameraResponse, CameraUpdate
from services.mediamtx import (
    add_camera_path,
    update_camera_path,
    remove_camera_path,
    sanitize_path_name,
    list_active_paths,
    get_path_status,
    set_recording_enabled,
    get_recording_status
)
from services.network_scanner import (
    discover_cameras,
    DiscoveredCamera,
    get_local_network_range
)
from services.onvif_config import (
    get_camera_video_config,
    update_camera_video_config
)
import aiohttp
import asyncio


# Pydantic models for ONVIF configuration
class ONVIFCredentials(BaseModel):
    host: str
    port: int = 80
    username: str
    password: str


class VideoEncoderUpdate(BaseModel):
    host: str
    port: int = 80
    username: str
    password: str
    config_token: str
    encoding: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    framerate: Optional[int] = None
    bitrate: Optional[int] = None
    quality: Optional[float] = None
    gov_length: Optional[int] = None
    profile: Optional[str] = None


class RTSPTestRequest(BaseModel):
    """Request model for testing RTSP connection"""
    rtsp_url: str
    timeout: int = 5


router = APIRouter(
    prefix="/api/cameras",
    tags=["cameras"],
    responses={404: {"description": "Not found"}},
)


def get_recording_path(tenant_id: int, location_id: int, camera_id: int) -> str:
    """Generate the recording path for a camera based on tenant/location structure"""
    return f"/recordings/tenant_{tenant_id}/location_{location_id}/camera_{camera_id}"


@router.post("/test-rtsp")
async def test_rtsp_connection(request: RTSPTestRequest):
    """
    Test if an RTSP URL is accessible and returns a valid stream.
    Returns connection status and basic stream info.
    """
    rtsp_url = request.rtsp_url
    timeout = request.timeout
    
    try:
        # Try to connect using ffprobe to validate the stream
        import subprocess
        
        # Use ffprobe to test the stream
        cmd = [
            "ffprobe",
            "-v", "error",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-show_entries", "stream=codec_name,width,height,r_frame_rate",
            "-of", "json",
            "-timeout", str(timeout * 1000000)  # Convert to microseconds
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout + 2
            )
            
            if process.returncode == 0:
                import json
                info = json.loads(stdout.decode())
                streams = info.get("streams", [])
                
                video_info = None
                for stream in streams:
                    if stream.get("codec_name") in ["h264", "h265", "hevc", "mjpeg"]:
                        video_info = {
                            "codec": stream.get("codec_name"),
                            "width": stream.get("width"),
                            "height": stream.get("height"),
                            "framerate": stream.get("r_frame_rate")
                        }
                        break
                
                return {
                    "success": True,
                    "message": "Connection successful",
                    "video_info": video_info
                }
            else:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                return {
                    "success": False,
                    "message": f"Failed to connect: {error_msg[:200]}",
                    "video_info": None
                }
                
        except asyncio.TimeoutError:
            process.kill()
            return {
                "success": False,
                "message": "Connection timeout",
                "video_info": None
            }
            
    except FileNotFoundError:
        # ffprobe not available, try simple socket test
        try:
            # Parse RTSP URL to get host and port
            import re
            match = re.match(r'rtsp://(?:[^:@]+(?::[^@]+)?@)?([^:/]+)(?::(\d+))?', rtsp_url)
            if match:
                host = match.group(1)
                port = int(match.group(2) or 554)
                
                # Try TCP connection
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout
                )
                writer.close()
                await writer.wait_closed()
                
                return {
                    "success": True,
                    "message": "Port is open (ffprobe not available for full test)",
                    "video_info": None
                }
        except Exception as e:
            pass
        
        return {
            "success": False,
            "message": "Cannot test connection (ffprobe not available)",
            "video_info": None
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "video_info": None
        }


@router.post("", response_model=CameraResponse)
async def create_camera(camera: CameraCreate, db: AsyncSession = Depends(get_db)):
    # Validate tenant_id if provided
    tenant = None
    if camera.tenant_id is not None:
        tenant_result = await db.execute(select(Tenant).filter(Tenant.id == camera.tenant_id))
        tenant = tenant_result.scalars().first()
        if tenant is None:
            raise HTTPException(status_code=400, detail="Invalid tenant_id: Tenant not found")
    
    # Validate location_id if provided
    location = None
    if camera.location_id is not None:
        location_result = await db.execute(select(Location).filter(Location.id == camera.location_id))
        location = location_result.scalars().first()
        if location is None:
            raise HTTPException(status_code=400, detail="Invalid location_id: Location not found")
        
        # Ensure location belongs to the specified tenant
        if camera.tenant_id is not None and location.tenant_id != camera.tenant_id:
            raise HTTPException(
                status_code=400, 
                detail="Location does not belong to the specified tenant"
            )
    
    # Check for unique constraint: same name in same tenant/location
    if camera.tenant_id is not None and camera.location_id is not None:
        existing_query = select(Camera).filter(
            Camera.tenant_id == camera.tenant_id,
            Camera.location_id == camera.location_id,
            Camera.name == camera.name
        )
        existing_result = await db.execute(existing_query)
        if existing_result.scalars().first() is not None:
            raise HTTPException(
                status_code=400,
                detail="A camera with this name already exists in this location"
            )
    
    # Create camera in database
    db_camera = Camera(
        name=camera.name, 
        rtsp_url=camera.rtsp_url, 
        is_active=camera.is_active,
        stream_mode=camera.stream_mode,
        user_id=camera.user_id,
        tenant_id=camera.tenant_id,
        location_id=camera.location_id
    )
    db.add(db_camera)
    await db.commit()
    await db.refresh(db_camera)
    
    # Add camera path to MediaMTX with intelligent mode detection
    # Pass tenant_slug and location_name for recording path organization
    path_name = sanitize_path_name(camera.name)
    tenant_slug = tenant.slug if tenant else None
    location_name = location.name if location else None
    
    success, final_mode = await add_camera_path(
        path_name, 
        camera.rtsp_url, 
        camera.stream_mode,
        tenant_slug=tenant_slug,
        location_name=location_name
    )
    
    # Update the stream_mode in database if auto-detection changed it
    if camera.stream_mode == "auto" and final_mode in ["direct", "ffmpeg"]:
        db_camera.stream_mode = final_mode
        await db.commit()
        await db.refresh(db_camera)
        print(f"Camera {camera.name}: auto-detected mode is '{final_mode}'")
    
    if not success:
        print(f"Warning: Failed to add camera path to MediaMTX for camera {camera.name}")
    
    return db_camera

@router.get("", response_model=List[CameraResponse])
async def read_cameras(
    skip: int = 0, 
    limit: int = 100, 
    user_id: Optional[str] = Query(None, description="Filter cameras by user ID"),
    tenant_id: Optional[int] = Query(None, description="Filter cameras by tenant ID"),
    location_id: Optional[int] = Query(None, description="Filter cameras by location ID"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Camera)
    if user_id:
        query = query.filter(Camera.user_id == user_id)
    if tenant_id:
        query = query.filter(Camera.tenant_id == tenant_id)
    if location_id:
        query = query.filter(Camera.location_id == location_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    cameras = result.scalars().all()
    return cameras

@router.get("/{camera_id}", response_model=CameraResponse)
async def read_camera(camera_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalars().first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera

@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(camera_id: int, camera: CameraUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    db_camera = result.scalars().first()
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    old_path_name = sanitize_path_name(db_camera.name)
    
    # Validate tenant_id if provided
    new_tenant_id = camera.tenant_id if camera.tenant_id is not None else db_camera.tenant_id
    new_location_id = camera.location_id if camera.location_id is not None else db_camera.location_id
    
    if camera.tenant_id is not None:
        tenant_result = await db.execute(select(Tenant).filter(Tenant.id == camera.tenant_id))
        tenant = tenant_result.scalars().first()
        if tenant is None:
            raise HTTPException(status_code=400, detail="Invalid tenant_id: Tenant not found")
    
    # Validate location_id if provided
    if camera.location_id is not None:
        location_result = await db.execute(select(Location).filter(Location.id == camera.location_id))
        location = location_result.scalars().first()
        if location is None:
            raise HTTPException(status_code=400, detail="Invalid location_id: Location not found")
        
        # Ensure location belongs to the specified tenant
        if new_tenant_id is not None and location.tenant_id != new_tenant_id:
            raise HTTPException(
                status_code=400, 
                detail="Location does not belong to the specified tenant"
            )
    
    # Check unique constraint if name is being changed
    new_name = camera.name if camera.name is not None else db_camera.name
    if new_tenant_id is not None and new_location_id is not None:
        if camera.name is not None or camera.tenant_id is not None or camera.location_id is not None:
            existing_query = select(Camera).filter(
                Camera.tenant_id == new_tenant_id,
                Camera.location_id == new_location_id,
                Camera.name == new_name,
                Camera.id != camera_id  # Exclude current camera
            )
            existing_result = await db.execute(existing_query)
            if existing_result.scalars().first() is not None:
                raise HTTPException(
                    status_code=400,
                    detail="A camera with this name already exists in this location"
                )
    
    # Update fields if provided
    if camera.name is not None:
        db_camera.name = camera.name
    if camera.rtsp_url is not None:
        db_camera.rtsp_url = camera.rtsp_url
    if camera.is_active is not None:
        db_camera.is_active = camera.is_active
    if camera.stream_mode is not None:
        db_camera.stream_mode = camera.stream_mode
    if camera.tenant_id is not None:
        db_camera.tenant_id = camera.tenant_id
    if camera.location_id is not None:
        db_camera.location_id = camera.location_id
    
    new_path_name = sanitize_path_name(db_camera.name)
    mode = db_camera.stream_mode
    
    # If name changed, remove old path
    if old_path_name != new_path_name:
        await remove_camera_path(old_path_name)
    
    # Update or create path with the current mode
    success, final_mode = await update_camera_path(new_path_name, db_camera.rtsp_url, mode)
    
    # Update mode if auto-detection changed it
    if mode == "auto" and final_mode in ["direct", "ffmpeg"]:
        db_camera.stream_mode = final_mode
    
    await db.commit()
    await db.refresh(db_camera)
    return db_camera

@router.delete("/{camera_id}")
async def delete_camera(camera_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    db_camera = result.scalars().first()
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Remove camera path from MediaMTX
    path_name = sanitize_path_name(db_camera.name)
    await remove_camera_path(path_name)
    
    await db.delete(db_camera)
    await db.commit()
    return {"message": "Camera deleted successfully"}


@router.post("/{camera_id}/recording/toggle", response_model=CameraResponse)
async def toggle_camera_recording(camera_id: int, db: AsyncSession = Depends(get_db)):
    """
    Toggle recording on/off for a camera.
    
    This pauses or resumes recording without stopping the stream.
    The camera will still be visible in live view, but won't save to disk.
    """
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    db_camera = result.scalars().first()
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Toggle recording state
    new_state = not db_camera.is_recording
    path_name = sanitize_path_name(db_camera.name)
    
    # Update MediaMTX
    success = await set_recording_enabled(path_name, new_state)
    if not success:
        raise HTTPException(
            status_code=500, 
            detail="Failed to update recording state in MediaMTX"
        )
    
    # Update database
    db_camera.is_recording = new_state
    await db.commit()
    await db.refresh(db_camera)
    
    return db_camera


@router.post("/{camera_id}/recording/start", response_model=CameraResponse)
async def start_camera_recording(camera_id: int, db: AsyncSession = Depends(get_db)):
    """
    Start recording for a camera.
    """
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    db_camera = result.scalars().first()
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    if db_camera.is_recording:
        return db_camera  # Already recording
    
    path_name = sanitize_path_name(db_camera.name)
    success = await set_recording_enabled(path_name, True)
    if not success:
        raise HTTPException(
            status_code=500, 
            detail="Failed to start recording in MediaMTX"
        )
    
    db_camera.is_recording = True
    await db.commit()
    await db.refresh(db_camera)
    
    return db_camera


@router.post("/{camera_id}/recording/stop", response_model=CameraResponse)
async def stop_camera_recording(camera_id: int, db: AsyncSession = Depends(get_db)):
    """
    Stop recording for a camera.
    
    The camera stream will continue to be available for live view,
    but no new recordings will be saved to disk.
    """
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    db_camera = result.scalars().first()
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    if not db_camera.is_recording:
        return db_camera  # Already stopped
    
    path_name = sanitize_path_name(db_camera.name)
    success = await set_recording_enabled(path_name, False)
    if not success:
        raise HTTPException(
            status_code=500, 
            detail="Failed to stop recording in MediaMTX"
        )
    
    db_camera.is_recording = False
    await db.commit()
    await db.refresh(db_camera)
    
    return db_camera


@router.get("/{camera_id}/recording/status")
async def get_camera_recording_status(camera_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get the recording status of a camera.
    
    Returns both the database state and the actual MediaMTX state.
    """
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    db_camera = result.scalars().first()
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    path_name = sanitize_path_name(db_camera.name)
    mediamtx_status = await get_recording_status(path_name)
    
    return {
        "camera_id": camera_id,
        "camera_name": db_camera.name,
        "db_recording": db_camera.is_recording,
        "mediamtx_recording": mediamtx_status,
        "in_sync": db_camera.is_recording == mediamtx_status if mediamtx_status is not None else None
    }

@router.get("/{camera_id}/stream")
async def get_camera_stream(camera_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalars().first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Use the sanitized camera name as the stream path
    stream_name = sanitize_path_name(camera.name)
    hls_url = f"http://localhost:8888/{stream_name}/index.m3u8"
    
    return {"stream_url": hls_url}


@router.get("/streams/active")
async def get_active_streams():
    """Get all active streams from MediaMTX."""
    paths = await list_active_paths()
    return {"streams": paths}


@router.post("/sync")
async def sync_cameras_to_mediamtx(db: AsyncSession = Depends(get_db)):
    """
    Synchronize all cameras from database to MediaMTX.
    Uses intelligent mode detection for cameras set to 'auto'.
    """
    # Get all active cameras with their tenant and location info
    result = await db.execute(
        select(Camera, Tenant, Location)
        .outerjoin(Tenant, Camera.tenant_id == Tenant.id)
        .outerjoin(Location, Camera.location_id == Location.id)
        .filter(Camera.is_active == True)
    )
    rows = result.all()
    
    synced = []
    failed = []
    
    for camera, tenant, location in rows:
        path_name = sanitize_path_name(camera.name)
        mode = camera.stream_mode or "auto"
        tenant_slug = tenant.slug if tenant else None
        location_name = location.name if location else None
        
        success, final_mode = await add_camera_path(
            path_name, 
            camera.rtsp_url, 
            mode,
            tenant_slug=tenant_slug,
            location_name=location_name
        )
        
        if success:
            synced.append({
                "name": camera.name,
                "mode": final_mode,
                "record_path": f"/recordings/{tenant_slug or 'default'}/{location_name or 'default'}/{path_name}" if tenant_slug else f"/recordings/{path_name}"
            })
            # Update mode in database if auto-detection changed it
            if mode == "auto" and final_mode in ["direct", "ffmpeg"]:
                camera.stream_mode = final_mode
        else:
            failed.append(camera.name)
    
    await db.commit()
    
    return {
        "message": f"Synced {len(synced)} cameras",
        "synced": synced,
        "failed": failed
    }


@router.post("/{camera_id}/resync")
async def resync_camera(camera_id: int, force_mode: str = None, db: AsyncSession = Depends(get_db)):
    """
    Re-sync a single camera to MediaMTX.
    
    Args:
        camera_id: ID of the camera to sync
        force_mode: Optional mode to force ('direct', 'ffmpeg', or 'auto')
    """
    # Get camera with tenant and location info
    result = await db.execute(
        select(Camera, Tenant, Location)
        .outerjoin(Tenant, Camera.tenant_id == Tenant.id)
        .outerjoin(Location, Camera.location_id == Location.id)
        .filter(Camera.id == camera_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    camera, tenant, location = row
    path_name = sanitize_path_name(camera.name)
    mode = force_mode if force_mode in ["direct", "ffmpeg", "auto"] else camera.stream_mode
    tenant_slug = tenant.slug if tenant else None
    location_name = location.name if location else None
    
    # Remove existing path first
    await remove_camera_path(path_name)
    
    # Re-add with specified mode and recording path
    success, final_mode = await add_camera_path(
        path_name, 
        camera.rtsp_url, 
        mode,
        tenant_slug=tenant_slug,
        location_name=location_name
    )
    
    if success and final_mode in ["direct", "ffmpeg"]:
        camera.stream_mode = final_mode
        await db.commit()
        await db.refresh(camera)
    
    return {
        "success": success,
        "camera": camera.name,
        "mode_requested": mode,
        "mode_used": final_mode
    }


@router.get("/{camera_id}/status")
async def get_camera_status(camera_id: int, db: AsyncSession = Depends(get_db)):
    """Get the current streaming status of a camera."""
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalars().first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    path_name = sanitize_path_name(camera.name)
    status = await get_path_status(path_name)
    
    return {
        "camera_id": camera.id,
        "name": camera.name,
        "stream_mode": camera.stream_mode,
        "is_active": camera.is_active,
        "mediamtx_status": status
    }


@router.get("/discover/network-info")
async def get_network_info():
    """Get information about the local network that will be scanned."""
    network_range = get_local_network_range()
    return {
        "network_range": network_range,
        "message": "This is the network range that will be scanned for cameras"
    }


@router.post("/discover")
async def discover_network_cameras(
    use_onvif: bool = Query(True, description="Use ONVIF WS-Discovery protocol"),
    use_port_scan: bool = Query(True, description="Use port scanning to find RTSP services"),
    network_range: Optional[str] = Query(None, description="Network range to scan (e.g., '192.168.1.0/24'). Auto-detected if not provided."),
    scan_timeout: float = Query(0.5, description="Timeout per host for port scanning (seconds)"),
    onvif_timeout: float = Query(3.0, description="Timeout for ONVIF discovery (seconds)")
):
    """
    Discover cameras on the local network.
    
    Uses two methods:
    1. **ONVIF WS-Discovery**: Finds ONVIF-compatible cameras via multicast. Fast and provides detailed device info.
    2. **Port Scanning**: Scans the network for devices with RTSP port (554) open. Slower but catches non-ONVIF cameras.
    
    Returns a list of discovered cameras with suggested RTSP URLs to try.
    """
    try:
        cameras = await discover_cameras(
            use_onvif=use_onvif,
            use_port_scan=use_port_scan,
            network_range=network_range,
            scan_timeout=scan_timeout,
            onvif_timeout=onvif_timeout
        )
        
        return {
            "count": len(cameras),
            "network_scanned": network_range or get_local_network_range(),
            "methods_used": {
                "onvif": use_onvif,
                "port_scan": use_port_scan
            },
            "cameras": [camera.to_dict() for camera in cameras]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


# ============================================================================
# ONVIF Configuration Endpoints
# ============================================================================

@router.post("/onvif/config")
async def get_onvif_video_config(credentials: ONVIFCredentials):
    """
    Get video encoder configuration from an ONVIF camera.
    
    Returns:
    - **profiles**: List of media profiles available
    - **encoder_configs**: Current video encoder configurations (resolution, bitrate, codec, etc.)
    - **options**: Available options for configuration (supported resolutions, bitrate range, etc.)
    
    Requires camera admin credentials for authentication.
    """
    try:
        result = await get_camera_video_config(
            host=credentials.host,
            port=credentials.port,
            username=credentials.username,
            password=credentials.password
        )
        
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ONVIF config: {str(e)}")


@router.put("/onvif/config")
async def update_onvif_video_config(update: VideoEncoderUpdate):
    """
    Update video encoder configuration on an ONVIF camera.
    
    Allows modifying:
    - **encoding**: Video codec (H264, H265)
    - **width/height**: Resolution
    - **framerate**: FPS limit
    - **bitrate**: Bitrate limit in kbps
    - **quality**: Quality level (1-100)
    - **gov_length**: GOP size / keyframe interval
    - **profile**: H264/H265 profile (Baseline, Main, High)
    
    Only provided parameters will be updated; others remain unchanged.
    Changes are persisted to the camera's configuration.
    
    **Note**: The camera may need to restart the stream for changes to take effect.
    """
    try:
        result = await update_camera_video_config(
            host=update.host,
            port=update.port,
            username=update.username,
            password=update.password,
            config_token=update.config_token,
            encoding=update.encoding,
            width=update.width,
            height=update.height,
            framerate=update.framerate,
            bitrate=update.bitrate,
            quality=update.quality,
            gov_length=update.gov_length,
            profile=update.profile
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400, 
                detail=result.get("error", "Failed to update configuration")
            )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update ONVIF config: {str(e)}")


@router.post("/onvif/test-connection")
async def test_onvif_connection(credentials: ONVIFCredentials):
    """
    Test ONVIF connection to a camera.
    
    Attempts to connect and retrieve basic profile information.
    Returns success status and number of profiles found.
    """
    try:
        result = await get_camera_video_config(
            host=credentials.host,
            port=credentials.port,
            username=credentials.username,
            password=credentials.password
        )
        
        if result.get("error"):
            return {
                "success": False,
                "error": result["error"],
                "profiles_count": 0
            }
        
        return {
            "success": True,
            "profiles_count": len(result.get("profiles", [])),
            "encoder_configs_count": len(result.get("encoder_configs", []))
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "profiles_count": 0
        }
