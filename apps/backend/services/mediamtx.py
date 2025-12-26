import httpx
import asyncio
import os
import re
from typing import Optional, Literal, Tuple

# Use localhost by default (for local dev), docker uses MEDIAMTX_API_URL env var
MEDIAMTX_API_URL = os.getenv("MEDIAMTX_API_URL", "http://localhost:9997")

# Time to wait for stream to become ready before trying FFmpeg fallback
STREAM_READY_TIMEOUT = 15  # seconds
STREAM_CHECK_INTERVAL = 2  # seconds


def sanitize_path_name(name: str) -> str:
    """Convert camera name to a valid path name for MediaMTX."""
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', name.replace(' ', '_'))
    return sanitized.lower()


def _build_record_path(
    tenant_slug: Optional[str], 
    location_name: Optional[str], 
    camera_name: str
) -> str:
    """
    Build the recording path following the structure: /recordings/tenant/location/%path
    
    MediaMTX requires %path in recordPath, which it replaces with the stream path name.
    
    Args:
        tenant_slug: Tenant identifier (e.g., 'acme-corp')
        location_name: Location name (e.g., 'headquarters')
        camera_name: Camera path name (not used directly, %path is used instead)
    
    Returns:
        Recording path like '/recordings/acme-corp/headquarters/%path'
        Falls back to '/recordings/%path' if tenant/location not provided
    """
    parts = ["/recordings"]
    
    if tenant_slug:
        parts.append(sanitize_path_name(tenant_slug))
        if location_name:
            parts.append(sanitize_path_name(location_name))
    
    # MediaMTX requires %path - it will be replaced with the stream path name
    parts.append("%path")
    
    return "/".join(parts)


async def _add_direct_path(
    path_name: str, 
    rtsp_url: str, 
    enable_recording: bool = True,
    record_path: Optional[str] = None
) -> bool:
    """Add a camera using direct RTSP connection."""
    config = {
        "source": rtsp_url,
        "sourceOnDemand": False,
    }
    
    # Add recording configuration
    if enable_recording:
        # Use custom record_path if provided, otherwise default to path name
        actual_record_path = record_path or f"/recordings/{path_name}"
        config.update({
            "record": True,
            "recordPath": f"{actual_record_path}/%Y-%m-%d_%H-%M-%S",
            "recordFormat": "fmp4",
            "recordSegmentDuration": "30m",
            "recordDeleteAfter": "7d",
        })
    
    try:
        async with httpx.AsyncClient() as client:
            # First delete if exists
            await client.delete(
                f"{MEDIAMTX_API_URL}/v3/config/paths/delete/{path_name}",
                timeout=5.0
            )
            
            # Add the path
            response = await client.post(
                f"{MEDIAMTX_API_URL}/v3/config/paths/add/{path_name}",
                json=config,
                timeout=10.0
            )
            
            return response.status_code == 200
    except Exception as e:
        print(f"Error adding direct path: {e}")
        return False


async def _add_ffmpeg_path(
    path_name: str, 
    rtsp_url: str, 
    enable_recording: bool = True,
    record_path: Optional[str] = None
) -> bool:
    """Add a camera using FFmpeg proxy (solves back channel issues).
    
    Uses runOnInit instead of runOnDemand so the stream runs continuously
    and can record even when no one is watching.
    """
    # FFmpeg command that avoids back channel negotiation
    ffmpeg_cmd = f'ffmpeg -rtsp_transport tcp -i {rtsp_url} -c copy -f rtsp rtsp://localhost:$RTSP_PORT/$MTX_PATH'
    
    config = {
        # Use runOnInit for continuous streaming (required for recording)
        "runOnInit": ffmpeg_cmd,
        "runOnInitRestart": True,
    }
    
    # Add recording configuration
    if enable_recording:
        # Use custom record_path if provided, otherwise default to path name
        actual_record_path = record_path or f"/recordings/{path_name}"
        config.update({
            "record": True,
            "recordPath": f"{actual_record_path}/%Y-%m-%d_%H-%M-%S",
            "recordFormat": "fmp4",
            "recordSegmentDuration": "30m",
            "recordDeleteAfter": "7d",
        })
    
    try:
        async with httpx.AsyncClient() as client:
            # First delete if exists
            await client.delete(
                f"{MEDIAMTX_API_URL}/v3/config/paths/delete/{path_name}",
                timeout=5.0
            )
            
            # Add the path with FFmpeg
            response = await client.post(
                f"{MEDIAMTX_API_URL}/v3/config/paths/add/{path_name}",
                json=config,
                timeout=10.0
            )
            
            print(f"FFmpeg path add response: {response.status_code} - {response.text}")
            return response.status_code == 200
    except Exception as e:
        print(f"Error adding FFmpeg path: {e}")
        return False


async def _check_path_ready(path_name: str, timeout: int = STREAM_READY_TIMEOUT) -> bool:
    """
    Check if a path becomes ready within timeout period.
    
    Returns True if stream is ready, False if timeout or error.
    """
    elapsed = 0
    
    try:
        async with httpx.AsyncClient() as client:
            while elapsed < timeout:
                response = await client.get(
                    f"{MEDIAMTX_API_URL}/v3/paths/list",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    
                    for item in items:
                        if item.get("name") == path_name:
                            if item.get("ready", False):
                                print(f"Path {path_name} is ready!")
                                return True
                
                await asyncio.sleep(STREAM_CHECK_INTERVAL)
                elapsed += STREAM_CHECK_INTERVAL
                print(f"Waiting for {path_name} to be ready... ({elapsed}s/{timeout}s)")
    except Exception as e:
        print(f"Error checking path ready: {e}")
    
    return False


async def add_camera_path(
    path_name: str, 
    rtsp_url: str, 
    mode: Literal["auto", "direct", "ffmpeg"] = "auto",
    tenant_slug: Optional[str] = None,
    location_name: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Add a new camera path to MediaMTX with intelligent mode selection.
    
    Args:
        path_name: The name for the stream path (e.g., 'living_room')
        rtsp_url: The RTSP URL of the camera source
        mode: Connection mode - 'auto', 'direct', or 'ffmpeg'
        tenant_slug: Optional tenant slug for recording path organization
        location_name: Optional location name for recording path organization
    
    Returns:
        Tuple of (success: bool, final_mode: str)
        final_mode indicates which mode was used ('direct' or 'ffmpeg')
    """
    print(f"Adding camera path {path_name} with mode={mode}")
    
    # Build the recording path: /recordings/tenant/location/camera
    record_path = _build_record_path(tenant_slug, location_name, path_name)
    print(f"Recording path: {record_path}")
    
    if mode == "ffmpeg":
        # User explicitly wants FFmpeg
        success = await _add_ffmpeg_path(path_name, rtsp_url, record_path=record_path)
        return (success, "ffmpeg")
    
    if mode == "direct":
        # User explicitly wants direct RTSP
        success = await _add_direct_path(path_name, rtsp_url, record_path=record_path)
        return (success, "direct")
    
    # Auto mode: Try direct first, fallback to FFmpeg if it fails
    print(f"Auto mode: Trying direct RTSP for {path_name}...")
    
    # Try direct RTSP first
    if not await _add_direct_path(path_name, rtsp_url, record_path=record_path):
        print(f"Failed to add direct path for {path_name}, trying FFmpeg...")
        success = await _add_ffmpeg_path(path_name, rtsp_url, record_path=record_path)
        return (success, "ffmpeg" if success else "failed")
    
    # Wait and check if stream becomes ready
    if await _check_path_ready(path_name, timeout=STREAM_READY_TIMEOUT):
        print(f"Direct RTSP works for {path_name}")
        return (True, "direct")
    
    # Direct didn't work, fallback to FFmpeg
    print(f"Direct RTSP failed for {path_name}, switching to FFmpeg proxy...")
    success = await _add_ffmpeg_path(path_name, rtsp_url, record_path=record_path)
    
    if success:
        # Give FFmpeg a moment to start
        await asyncio.sleep(3)
        print(f"FFmpeg proxy configured for {path_name}")
        return (True, "ffmpeg")
    
    return (False, "failed")


async def update_camera_path(
    path_name: str, 
    rtsp_url: str,
    mode: Literal["auto", "direct", "ffmpeg"] = "auto",
    tenant_slug: Optional[str] = None,
    location_name: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Update an existing camera path in MediaMTX.
    
    Args:
        path_name: The name of the stream path to update
        rtsp_url: The new RTSP URL of the camera source
        mode: Connection mode
        tenant_slug: Optional tenant slug for recording path organization
        location_name: Optional location name for recording path organization
    
    Returns:
        Tuple of (success: bool, final_mode: str)
    """
    # For updates, we just remove and re-add with the new settings
    await remove_camera_path(path_name)
    return await add_camera_path(path_name, rtsp_url, mode, tenant_slug, location_name)


async def remove_camera_path(path_name: str) -> bool:
    """
    Remove a camera path from MediaMTX.
    
    Args:
        path_name: The name of the stream path to remove
    
    Returns:
        True if successful, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{MEDIAMTX_API_URL}/v3/config/paths/delete/{path_name}",
                timeout=10.0
            )
            
            # 200 = deleted, 404 = didn't exist (which is fine)
            return response.status_code in [200, 404]
            
    except Exception as e:
        print(f"Error removing camera path from MediaMTX: {e}")
        return False


async def get_camera_path(path_name: str) -> Optional[dict]:
    """
    Get information about a camera path from MediaMTX.
    
    Args:
        path_name: The name of the stream path
    
    Returns:
        Path configuration dict if exists, None otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MEDIAMTX_API_URL}/v3/config/paths/get/{path_name}",
                timeout=10.0
            )
            
            if response.status_code == 200:
                return response.json()
            return None
            
    except Exception as e:
        print(f"Error getting camera path from MediaMTX: {e}")
        return None


async def list_active_paths() -> list:
    """
    List all active paths in MediaMTX.
    
    Returns:
        List of active path dicts
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MEDIAMTX_API_URL}/v3/paths/list",
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("items", [])
            return []
            
    except Exception as e:
        print(f"Error listing paths from MediaMTX: {e}")
        return []


async def get_path_status(path_name: str) -> Optional[dict]:
    """
    Get runtime status of a camera path from MediaMTX.
    
    Args:
        path_name: The name of the stream path
    
    Returns:
        Path status dict if exists, None otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MEDIAMTX_API_URL}/v3/paths/list",
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", []):
                    if item.get("name") == path_name:
                        return {
                            "ready": item.get("ready", False),
                            "tracks": item.get("tracks", []),
                            "bytesReceived": item.get("bytesReceived", 0),
                            "readers": len(item.get("readers", []))
                        }
            return None
            
    except Exception as e:
        print(f"Error getting path status from MediaMTX: {e}")
        return None


async def set_recording_enabled(path_name: str, enabled: bool) -> bool:
    """
    Enable or disable recording for a camera path.
    
    This uses MediaMTX PATCH API to update only the record field
    without changing other configuration.
    
    Args:
        path_name: The name of the stream path
        enabled: True to enable recording, False to disable
    
    Returns:
        True if successful, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            # Use PATCH to update only the record field
            response = await client.patch(
                f"{MEDIAMTX_API_URL}/v3/config/paths/patch/{path_name}",
                json={"record": enabled},
                timeout=10.0
            )
            
            if response.status_code == 200:
                print(f"Recording {'enabled' if enabled else 'disabled'} for path: {path_name}")
                return True
            else:
                print(f"Failed to update recording for {path_name}: {response.status_code} - {response.text}")
                return False
            
    except Exception as e:
        print(f"Error updating recording for {path_name}: {e}")
        return False


async def get_recording_status(path_name: str) -> Optional[bool]:
    """
    Get the current recording status for a camera path.
    
    Args:
        path_name: The name of the stream path
    
    Returns:
        True if recording is enabled, False if disabled, None if path not found
    """
    try:
        config = await get_camera_path(path_name)
        if config:
            return config.get("record", False)
        return None
    except Exception as e:
        print(f"Error getting recording status for {path_name}: {e}")
        return None
