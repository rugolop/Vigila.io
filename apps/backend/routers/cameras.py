from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel

from database import get_db
from models import Camera
from schemas import CameraCreate, CameraResponse, CameraUpdate
from services.mediamtx import (
    add_camera_path,
    update_camera_path,
    remove_camera_path,
    sanitize_path_name,
    list_active_paths,
    get_path_status
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


router = APIRouter(
    prefix="/cameras",
    tags=["cameras"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=CameraResponse)
async def create_camera(camera: CameraCreate, db: AsyncSession = Depends(get_db)):
    # Create camera in database
    db_camera = Camera(
        name=camera.name, 
        rtsp_url=camera.rtsp_url, 
        is_active=camera.is_active,
        stream_mode=camera.stream_mode,
        user_id=camera.user_id
    )
    db.add(db_camera)
    await db.commit()
    await db.refresh(db_camera)
    
    # Add camera path to MediaMTX with intelligent mode detection
    path_name = sanitize_path_name(camera.name)
    success, final_mode = await add_camera_path(path_name, camera.rtsp_url, camera.stream_mode)
    
    # Update the stream_mode in database if auto-detection changed it
    if camera.stream_mode == "auto" and final_mode in ["direct", "ffmpeg"]:
        db_camera.stream_mode = final_mode
        await db.commit()
        await db.refresh(db_camera)
        print(f"Camera {camera.name}: auto-detected mode is '{final_mode}'")
    
    if not success:
        print(f"Warning: Failed to add camera path to MediaMTX for camera {camera.name}")
    
    return db_camera

@router.get("/", response_model=List[CameraResponse])
async def read_cameras(
    skip: int = 0, 
    limit: int = 100, 
    user_id: Optional[str] = Query(None, description="Filter cameras by user ID"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Camera)
    if user_id:
        query = query.filter(Camera.user_id == user_id)
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
    
    # Update fields if provided
    if camera.name is not None:
        db_camera.name = camera.name
    if camera.rtsp_url is not None:
        db_camera.rtsp_url = camera.rtsp_url
    if camera.is_active is not None:
        db_camera.is_active = camera.is_active
    if camera.stream_mode is not None:
        db_camera.stream_mode = camera.stream_mode
    
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
    result = await db.execute(select(Camera).filter(Camera.is_active == True))
    cameras = result.scalars().all()
    
    synced = []
    failed = []
    
    for camera in cameras:
        path_name = sanitize_path_name(camera.name)
        mode = camera.stream_mode or "auto"
        
        success, final_mode = await add_camera_path(path_name, camera.rtsp_url, mode)
        
        if success:
            synced.append({
                "name": camera.name,
                "mode": final_mode
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
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalars().first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    path_name = sanitize_path_name(camera.name)
    mode = force_mode if force_mode in ["direct", "ffmpeg", "auto"] else camera.stream_mode
    
    # Remove existing path first
    await remove_camera_path(path_name)
    
    # Re-add with specified mode
    success, final_mode = await add_camera_path(path_name, camera.rtsp_url, mode)
    
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
