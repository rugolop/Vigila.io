"""
Vigila.io Local Agent - Stream Relay
Relays RTSP streams from local cameras to the remote Vigila.io server.
"""
import asyncio
import subprocess
import logging
from dataclasses import dataclass
from typing import Dict, Optional
import shutil

logger = logging.getLogger(__name__)


@dataclass
class StreamRelay:
    """Manages an FFmpeg process that relays a stream."""
    camera_id: str
    local_rtsp_url: str
    remote_rtsp_url: str
    process: Optional[subprocess.Popen] = None
    
    def is_running(self) -> bool:
        """Check if the relay process is running."""
        return self.process is not None and self.process.poll() is None


class StreamRelayManager:
    """Manages multiple stream relays."""
    
    def __init__(self, server_rtsp_url: str):
        """
        Initialize the relay manager.
        
        Args:
            server_rtsp_url: Base RTSP URL of the remote MediaMTX server
                            e.g., rtsp://api.vigila.io:8554
        """
        self.server_rtsp_url = server_rtsp_url.rstrip("/")
        self.relays: Dict[str, StreamRelay] = {}
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """Verify FFmpeg is installed."""
        if not shutil.which("ffmpeg"):
            raise RuntimeError(
                "FFmpeg is not installed. Please install it:\n"
                "  - Windows: choco install ffmpeg\n"
                "  - macOS: brew install ffmpeg\n"
                "  - Linux: apt install ffmpeg"
            )
        logger.info("FFmpeg found")
    
    def start_relay(
        self, 
        camera_id: str, 
        local_rtsp_url: str,
        stream_key: str = None
    ) -> bool:
        """
        Start relaying a local camera stream to the remote server.
        
        Args:
            camera_id: Unique identifier for this camera
            local_rtsp_url: RTSP URL of the local camera
            stream_key: Optional stream key for the remote server
        
        Returns:
            True if relay started successfully
        """
        # Stop existing relay if any
        self.stop_relay(camera_id)
        
        # Build remote URL with stream key
        stream_path = stream_key or camera_id
        remote_url = f"{self.server_rtsp_url}/{stream_path}"
        
        # FFmpeg command to relay stream
        # -rtsp_transport tcp: Use TCP for more reliable streaming
        # -c copy: No transcoding, just relay
        # -f rtsp: Output format
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-rtsp_transport", "tcp",
            "-i", local_rtsp_url,
            "-c", "copy",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            remote_url
        ]
        
        try:
            logger.info(f"Starting relay for {camera_id}: {local_rtsp_url} -> {remote_url}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )
            
            # Check if process started successfully
            asyncio.get_event_loop().call_later(2, self._check_process, camera_id)
            
            relay = StreamRelay(
                camera_id=camera_id,
                local_rtsp_url=local_rtsp_url,
                remote_rtsp_url=remote_url,
                process=process
            )
            
            self.relays[camera_id] = relay
            logger.info(f"Relay started for {camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start relay for {camera_id}: {e}")
            return False
    
    def _check_process(self, camera_id: str):
        """Check if a relay process is still running after startup."""
        relay = self.relays.get(camera_id)
        if relay and not relay.is_running():
            stderr = relay.process.stderr.read().decode() if relay.process.stderr else ""
            logger.error(f"Relay for {camera_id} died: {stderr}")
    
    def stop_relay(self, camera_id: str) -> bool:
        """
        Stop a relay.
        
        Args:
            camera_id: ID of the camera relay to stop
        
        Returns:
            True if relay was stopped
        """
        relay = self.relays.get(camera_id)
        if relay and relay.process:
            try:
                relay.process.terminate()
                relay.process.wait(timeout=5)
                logger.info(f"Relay stopped for {camera_id}")
            except subprocess.TimeoutExpired:
                relay.process.kill()
                logger.warning(f"Relay killed for {camera_id}")
            except Exception as e:
                logger.error(f"Error stopping relay for {camera_id}: {e}")
            
            del self.relays[camera_id]
            return True
        return False
    
    def stop_all(self):
        """Stop all relays."""
        for camera_id in list(self.relays.keys()):
            self.stop_relay(camera_id)
    
    def get_status(self) -> Dict[str, bool]:
        """Get status of all relays."""
        return {
            camera_id: relay.is_running()
            for camera_id, relay in self.relays.items()
        }
    
    def restart_dead_relays(self):
        """Restart any relays that have died."""
        for camera_id, relay in list(self.relays.items()):
            if not relay.is_running():
                logger.warning(f"Relay for {camera_id} died, restarting...")
                self.start_relay(
                    camera_id,
                    relay.local_rtsp_url,
                    camera_id  # Use camera_id as stream key
                )
