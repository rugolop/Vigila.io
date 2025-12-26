"""
Vigila.io - Agent Router
Handles local agent registration, heartbeat, and camera management.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import secrets
import io
import zipfile
import os

from database import get_db
from models import Tenant, Location, Camera
from services.mediamtx import add_camera_path, remove_camera_path, sanitize_path_name


router = APIRouter(
    prefix="/agents",
    tags=["agents"],
    responses={404: {"description": "Not found"}},
)


# =============================================================================
# Pydantic Models
# =============================================================================

class AgentRegisterRequest(BaseModel):
    """Request to register a new agent."""
    name: str
    token: str
    local_ip: str
    version: str = "1.0.0"


class AgentRegisterResponse(BaseModel):
    """Response after successful registration."""
    agent_id: str
    rtsp_server_url: str
    message: str


class AgentHeartbeatRequest(BaseModel):
    """Heartbeat request from agent."""
    token: str
    cameras_count: int
    relay_status: dict
    timestamp: str


class AgentHeartbeatResponse(BaseModel):
    """Response to heartbeat with commands."""
    status: str
    commands: List[dict]


class DiscoveredCameraInfo(BaseModel):
    """Camera discovered by an agent."""
    ip: str
    port: int
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    name: str = ""
    rtsp_url: Optional[str] = None
    onvif_url: Optional[str] = None


class AgentCamerasRequest(BaseModel):
    """Request to report discovered cameras."""
    token: str
    cameras: List[DiscoveredCameraInfo]


class StartRelayRequest(BaseModel):
    """Request to start relaying a camera."""
    token: str
    camera_id: str
    rtsp_url: str
    camera_name: str
    tenant_id: int
    location_id: Optional[int] = None


# =============================================================================
# In-Memory Storage (In production, use Redis or database)
# =============================================================================

# Active agents: agent_id -> {name, token_hash, tenant_id, local_ip, last_seen, ...}
active_agents = {}

# Pending commands for agents: agent_id -> [commands]
pending_commands = {}

# Discovered cameras by agent: agent_id -> [cameras]
discovered_cameras_cache = {}


# =============================================================================
# Helper Functions
# =============================================================================

def verify_agent_token(token: str) -> Optional[dict]:
    """
    Verify agent token and return tenant info.
    Token format: tenant_id:secret
    """
    try:
        parts = token.split(":")
        if len(parts) != 2:
            return None
        
        tenant_id = int(parts[0])
        secret = parts[1]
        
        # In production, verify secret against database
        # For now, accept any well-formed token
        return {"tenant_id": tenant_id, "secret": secret}
    except:
        return None


def generate_agent_id() -> str:
    """Generate a unique agent ID."""
    return f"agent_{secrets.token_hex(8)}"


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/register", response_model=AgentRegisterResponse)
async def register_agent(
    request: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new local agent.
    
    The agent provides a token that identifies the tenant it belongs to.
    """
    # Verify token
    token_info = verify_agent_token(request.token)
    if not token_info:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    tenant_id = token_info["tenant_id"]
    
    # Verify tenant exists
    result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Generate agent ID
    agent_id = generate_agent_id()
    
    # Store agent info
    active_agents[agent_id] = {
        "name": request.name,
        "tenant_id": tenant_id,
        "tenant_slug": tenant.slug,
        "local_ip": request.local_ip,
        "version": request.version,
        "registered_at": datetime.utcnow().isoformat(),
        "last_seen": datetime.utcnow().isoformat(),
        "token_hash": hash(request.token)
    }
    
    # Initialize pending commands
    pending_commands[agent_id] = []
    
    # Get RTSP server URL from environment or use default
    import os
    rtsp_host = os.getenv("RTSP_PUBLIC_HOST", "localhost")
    rtsp_port = os.getenv("RTSP_PUBLIC_PORT", "8554")
    rtsp_server_url = f"rtsp://{rtsp_host}:{rtsp_port}"
    
    return AgentRegisterResponse(
        agent_id=agent_id,
        rtsp_server_url=rtsp_server_url,
        message=f"Agent '{request.name}' registered successfully for tenant '{tenant.name}'"
    )


@router.post("/{agent_id}/heartbeat", response_model=AgentHeartbeatResponse)
async def agent_heartbeat(
    agent_id: str,
    request: AgentHeartbeatRequest
):
    """
    Receive heartbeat from agent and return any pending commands.
    """
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Verify token
    if hash(request.token) != active_agents[agent_id]["token_hash"]:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Update last seen
    active_agents[agent_id]["last_seen"] = datetime.utcnow().isoformat()
    active_agents[agent_id]["cameras_count"] = request.cameras_count
    active_agents[agent_id]["relay_status"] = request.relay_status
    
    # Get and clear pending commands
    commands = pending_commands.get(agent_id, [])
    pending_commands[agent_id] = []
    
    return AgentHeartbeatResponse(
        status="ok",
        commands=commands
    )


@router.post("/{agent_id}/cameras")
async def report_discovered_cameras(
    agent_id: str,
    request: AgentCamerasRequest
):
    """
    Agent reports cameras discovered on the local network.
    """
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Verify token
    if hash(request.token) != active_agents[agent_id]["token_hash"]:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Store discovered cameras
    discovered_cameras_cache[agent_id] = [cam.dict() for cam in request.cameras]
    
    return {
        "status": "ok",
        "cameras_received": len(request.cameras)
    }


@router.get("/{agent_id}/discovered")
async def get_discovered_cameras(agent_id: str):
    """
    Get cameras discovered by an agent.
    """
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "agent_id": agent_id,
        "cameras": discovered_cameras_cache.get(agent_id, [])
    }


@router.post("/{agent_id}/discover")
async def trigger_discovery(agent_id: str):
    """
    Trigger camera discovery on an agent.
    """
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Add discover command to pending commands
    pending_commands.setdefault(agent_id, []).append({
        "type": "discover"
    })
    
    return {"status": "ok", "message": "Discovery command queued"}


@router.post("/{agent_id}/start-relay")
async def start_camera_relay(
    agent_id: str,
    request: StartRelayRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Command an agent to start relaying a camera stream.
    
    This also creates the camera in the database and configures MediaMTX.
    """
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent = active_agents[agent_id]
    
    # Verify token
    if hash(request.token) != agent["token_hash"]:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Get tenant and location info
    tenant_result = await db.execute(select(Tenant).filter(Tenant.id == request.tenant_id))
    tenant = tenant_result.scalars().first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    location = None
    if request.location_id:
        location_result = await db.execute(select(Location).filter(Location.id == request.location_id))
        location = location_result.scalars().first()
    
    # Create camera in database
    path_name = sanitize_path_name(request.camera_name)
    stream_key = f"{agent_id}_{path_name}"
    
    db_camera = Camera(
        name=request.camera_name,
        rtsp_url=request.rtsp_url,
        is_active=True,
        stream_mode="agent",  # New mode for agent-relayed cameras
        tenant_id=request.tenant_id,
        location_id=request.location_id
    )
    db.add(db_camera)
    await db.commit()
    await db.refresh(db_camera)
    
    # Configure MediaMTX to receive the stream
    # The stream key includes agent_id to avoid conflicts
    await add_camera_path(
        stream_key,
        f"publisher",  # Will receive from agent, not pull
        "direct",
        tenant_slug=tenant.slug,
        location_name=location.name if location else None
    )
    
    # Queue command for agent
    pending_commands.setdefault(agent_id, []).append({
        "type": "start_relay",
        "camera_id": str(db_camera.id),
        "rtsp_url": request.rtsp_url,
        "stream_key": stream_key
    })
    
    return {
        "status": "ok",
        "camera_id": db_camera.id,
        "stream_key": stream_key,
        "message": f"Relay command queued for camera '{request.camera_name}'"
    }


@router.post("/{agent_id}/stop-relay/{camera_id}")
async def stop_camera_relay(agent_id: str, camera_id: str):
    """
    Command an agent to stop relaying a camera stream.
    """
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Queue command for agent
    pending_commands.setdefault(agent_id, []).append({
        "type": "stop_relay",
        "camera_id": camera_id
    })
    
    return {"status": "ok", "message": f"Stop relay command queued for camera {camera_id}"}


@router.get("/")
async def list_agents(
    tenant_id: Optional[int] = None,
    x_user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List all active agents.
    
    - Super admins can see all agents (no tenant_id filter)
    - Regular admins see only their tenant's agents (tenant_id required)
    """
    agents = []
    now = datetime.utcnow()
    
    for agent_id, info in active_agents.items():
        # Filter by tenant if specified
        if tenant_id is not None and info["tenant_id"] != tenant_id:
            continue
            
        last_seen = datetime.fromisoformat(info["last_seen"])
        is_online = (now - last_seen) < timedelta(minutes=2)
        
        agents.append({
            "agent_id": agent_id,
            "name": info["name"],
            "tenant_id": info["tenant_id"],
            "tenant_slug": info.get("tenant_slug", ""),
            "local_ip": info["local_ip"],
            "version": info["version"],
            "is_online": is_online,
            "last_seen": info["last_seen"],
            "cameras_count": info.get("cameras_count", 0)
        })
    
    return {"agents": agents}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """
    Get details of a specific agent.
    """
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    info = active_agents[agent_id]
    last_seen = datetime.fromisoformat(info["last_seen"])
    is_online = (datetime.utcnow() - last_seen) < timedelta(minutes=2)
    
    return {
        "agent_id": agent_id,
        "name": info["name"],
        "tenant_id": info["tenant_id"],
        "tenant_slug": info["tenant_slug"],
        "local_ip": info["local_ip"],
        "version": info["version"],
        "is_online": is_online,
        "last_seen": info["last_seen"],
        "registered_at": info["registered_at"],
        "cameras_count": info.get("cameras_count", 0),
        "relay_status": info.get("relay_status", {})
    }


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """
    Unregister an agent.
    """
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    del active_agents[agent_id]
    pending_commands.pop(agent_id, None)
    discovered_cameras_cache.pop(agent_id, None)
    
    return {"status": "ok", "message": f"Agent {agent_id} unregistered"}


# =============================================================================
# Agent Download Endpoint
# =============================================================================

# Embedded agent source files
AGENT_FILES = {
    "agent.py": '''#!/usr/bin/env python3
"""
Vigila.io Local Agent

This agent runs on the user's local network and:
1. Registers with the remote Vigila.io server
2. Discovers cameras on the local network
3. Relays camera streams to the server
4. Maintains connection and handles commands from the server

Usage:
    python agent.py

Configuration:
    The .env file is pre-configured with your token and server URL.
"""
import asyncio
import json
import logging
import signal
import sys
from datetime import datetime
from typing import Optional, List, Dict

import httpx

from config import AgentConfig
from scanner import discover_cameras, get_local_ip, DiscoveredCamera
from relay import StreamRelayManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("vigila-agent")


class VigilaAgent:
    """Main agent class that coordinates all operations."""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent_id: Optional[str] = None
        self.registered = False
        self.running = False
        self.discovered_cameras: List[DiscoveredCamera] = []
        self.active_cameras: Dict[str, dict] = {}
        self.relay_manager: Optional[StreamRelayManager] = None
        logging.getLogger().setLevel(config.log_level)
    
    async def register(self) -> bool:
        """Register this agent with the Vigila.io server."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config.server_url}/api/agents/register",
                    json={
                        "name": self.config.agent_name,
                        "token": self.config.token,
                        "local_ip": get_local_ip(),
                        "version": "1.0.0"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.agent_id = data.get("agent_id")
                    self.registered = True
                    rtsp_url = data.get("rtsp_server_url", f"{self.config.server_url.replace('https', 'rtsp').replace('http', 'rtsp')}:8554")
                    self.relay_manager = StreamRelayManager(rtsp_url)
                    logger.info(f"Registered successfully! Agent ID: {self.agent_id}")
                    return True
                else:
                    logger.error(f"Registration failed: {response.status_code} - {response.text}")
                    return False
        except httpx.ConnectError:
            logger.error(f"Cannot connect to server at {self.config.server_url}")
            return False
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False
    
    async def heartbeat(self):
        """Send periodic heartbeat to the server."""
        while self.running:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.config.server_url}/api/agents/{self.agent_id}/heartbeat",
                        json={
                            "token": self.config.token,
                            "cameras_count": len(self.active_cameras),
                            "relay_status": self.relay_manager.get_status() if self.relay_manager else {},
                            "timestamp": datetime.utcnow().isoformat()
                        },
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        await self.process_commands(data.get("commands", []))
                    else:
                        logger.warning(f"Heartbeat failed: {response.status_code}")
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            await asyncio.sleep(self.config.heartbeat_interval)
    
    async def process_commands(self, commands: List[dict]):
        """Process commands received from the server."""
        for cmd in commands:
            cmd_type = cmd.get("type")
            
            if cmd_type == "discover":
                await self.discover_and_report()
            elif cmd_type == "start_relay":
                camera_id = cmd.get("camera_id")
                rtsp_url = cmd.get("rtsp_url")
                stream_key = cmd.get("stream_key")
                if camera_id and rtsp_url:
                    self.relay_manager.start_relay(camera_id, rtsp_url, stream_key)
                    self.active_cameras[camera_id] = {
                        "rtsp_url": rtsp_url,
                        "stream_key": stream_key,
                        "started_at": datetime.utcnow().isoformat()
                    }
            elif cmd_type == "stop_relay":
                camera_id = cmd.get("camera_id")
                if camera_id:
                    self.relay_manager.stop_relay(camera_id)
                    self.active_cameras.pop(camera_id, None)
            elif cmd_type == "restart_relay":
                camera_id = cmd.get("camera_id")
                if camera_id and camera_id in self.active_cameras:
                    info = self.active_cameras[camera_id]
                    self.relay_manager.stop_relay(camera_id)
                    self.relay_manager.start_relay(camera_id, info["rtsp_url"], info.get("stream_key"))
    
    async def discover_and_report(self):
        """Discover cameras and report to the server."""
        logger.info("Starting camera discovery...")
        self.discovered_cameras = await discover_cameras(network_range=self.config.network_range)
        
        try:
            async with httpx.AsyncClient() as client:
                cameras_data = [
                    {
                        "ip": cam.ip,
                        "port": cam.port,
                        "manufacturer": cam.manufacturer,
                        "model": cam.model,
                        "name": cam.name,
                        "rtsp_url": cam.rtsp_url,
                        "onvif_url": cam.onvif_url
                    }
                    for cam in self.discovered_cameras
                ]
                
                await client.post(
                    f"{self.config.server_url}/api/agents/{self.agent_id}/cameras",
                    json={"token": self.config.token, "cameras": cameras_data},
                    timeout=30.0
                )
                logger.info(f"Reported {len(cameras_data)} discovered cameras to server")
        except Exception as e:
            logger.error(f"Failed to report cameras: {e}")
    
    async def monitor_relays(self):
        """Monitor and restart dead relays."""
        while self.running:
            if self.relay_manager:
                self.relay_manager.restart_dead_relays()
            await asyncio.sleep(10)
    
    async def run(self):
        """Main run loop."""
        logger.info("=" * 50)
        logger.info("Vigila.io Local Agent Starting")
        logger.info(f"Agent Name: {self.config.agent_name}")
        logger.info(f"Server: {self.config.server_url}")
        logger.info(f"Local IP: {get_local_ip()}")
        logger.info("=" * 50)
        
        if not await self.register():
            logger.error("Failed to register with server. Exiting.")
            return
        
        self.running = True
        await self.discover_and_report()
        
        tasks = [
            asyncio.create_task(self.heartbeat()),
            asyncio.create_task(self.monitor_relays())
        ]
        
        logger.info("Agent is running. Press Ctrl+C to stop.")
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Cleanup on shutdown."""
        logger.info("Shutting down agent...")
        self.running = False
        if self.relay_manager:
            self.relay_manager.stop_all()
        logger.info("Agent stopped.")


def main():
    """Main entry point."""
    try:
        config = AgentConfig.from_env()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    agent = VigilaAgent(config)
    
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        agent.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    asyncio.run(agent.run())


if __name__ == "__main__":
    main()
''',

    "config.py": '''"""
Vigila.io Local Agent - Configuration
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    """Agent configuration loaded from environment variables."""
    token: str
    server_url: str
    agent_name: str
    local_port: int = 8554
    heartbeat_interval: int = 30
    network_range: str = None
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        token = os.getenv("VIGILA_TOKEN")
        server_url = os.getenv("VIGILA_SERVER_URL")
        agent_name = os.getenv("AGENT_NAME")
        
        if not token:
            raise ValueError("VIGILA_TOKEN is required. Get it from your Vigila.io dashboard.")
        if not server_url:
            raise ValueError("VIGILA_SERVER_URL is required.")
        if not agent_name:
            raise ValueError("AGENT_NAME is required.")
        
        return cls(
            token=token,
            server_url=server_url.rstrip("/"),
            agent_name=agent_name,
            local_port=int(os.getenv("LOCAL_PORT", "8554")),
            heartbeat_interval=int(os.getenv("HEARTBEAT_INTERVAL", "30")),
            network_range=os.getenv("NETWORK_RANGE"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
''',

    "scanner.py": '''"""
Vigila.io Local Agent - Network Scanner
Discovers cameras on the local network using ONVIF/WS-Discovery.
"""
import socket
import asyncio
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredCamera:
    """Represents a discovered camera on the local network."""
    ip: str
    port: int
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    name: str = ""
    rtsp_url: Optional[str] = None
    onvif_url: Optional[str] = None


def get_local_ip() -> str:
    """Get the local IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_network_range(local_ip: str = None) -> str:
    """Get the network range based on local IP."""
    if local_ip is None:
        local_ip = get_local_ip()
    parts = local_ip.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"


async def discover_onvif_cameras(timeout: int = 5) -> List[DiscoveredCamera]:
    """Discover cameras using WS-Discovery (ONVIF)."""
    cameras = []
    
    try:
        from wsdiscovery.discovery import ThreadedWSDiscovery
        
        wsd = ThreadedWSDiscovery()
        wsd.start()
        
        services = wsd.searchServices(types=["dn:NetworkVideoTransmitter"], timeout=timeout)
        
        for service in services:
            try:
                xaddrs = service.getXAddrs()
                if xaddrs:
                    for addr in xaddrs:
                        import re
                        match = re.search(r'//([^:/]+)', addr)
                        if match:
                            ip = match.group(1)
                            port = 80
                            port_match = re.search(r':(\d+)', addr)
                            if port_match:
                                port = int(port_match.group(1))
                            
                            camera = DiscoveredCamera(
                                ip=ip, port=port, onvif_url=addr,
                                manufacturer=service.getTypes()[0] if service.getTypes() else "ONVIF Device"
                            )
                            cameras.append(camera)
                            logger.info(f"Discovered ONVIF camera at {ip}:{port}")
                            break
            except Exception as e:
                logger.debug(f"Error parsing service: {e}")
        
        wsd.stop()
    except ImportError:
        logger.warning("wsdiscovery not installed, skipping ONVIF discovery")
    except Exception as e:
        logger.error(f"ONVIF discovery error: {e}")
    
    return cameras


async def scan_common_ports(network_range: str = None, timeout: float = 0.5) -> List[DiscoveredCamera]:
    """Scan common RTSP ports in the network."""
    cameras = []
    common_ports = [554, 8554, 80, 8080]
    
    if network_range is None:
        network_range = get_network_range()
    
    base_ip = network_range.split("/")[0]
    base_parts = base_ip.split(".")[:3]
    
    async def check_port(ip: str, port: int) -> Optional[DiscoveredCamera]:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return DiscoveredCamera(ip=ip, port=port)
        except:
            return None
    
    tasks = []
    for i in range(1, 255):
        ip = f"{base_parts[0]}.{base_parts[1]}.{base_parts[2]}.{i}"
        for port in common_ports:
            tasks.append(check_port(ip, port))
    
    logger.info(f"Scanning {network_range} for cameras...")
    results = await asyncio.gather(*tasks)
    
    found_ips = set()
    for result in results:
        if result and result.ip not in found_ips:
            cameras.append(result)
            found_ips.add(result.ip)
            logger.info(f"Found potential camera at {result.ip}:{result.port}")
    
    return cameras


async def discover_cameras(network_range: str = None, timeout: int = 5) -> List[DiscoveredCamera]:
    """Discover cameras using multiple methods."""
    all_cameras = []
    seen_ips = set()
    
    logger.info("Starting ONVIF discovery...")
    onvif_cameras = await discover_onvif_cameras(timeout=timeout)
    for cam in onvif_cameras:
        if cam.ip not in seen_ips:
            all_cameras.append(cam)
            seen_ips.add(cam.ip)
    
    if not all_cameras:
        logger.info("No ONVIF cameras found, scanning common ports...")
        port_cameras = await scan_common_ports(network_range, timeout=0.3)
        for cam in port_cameras:
            if cam.ip not in seen_ips:
                all_cameras.append(cam)
                seen_ips.add(cam.ip)
    
    logger.info(f"Total cameras discovered: {len(all_cameras)}")
    return all_cameras
''',

    "relay.py": '''"""
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
        return self.process is not None and self.process.poll() is None


class StreamRelayManager:
    """Manages multiple stream relays."""
    
    def __init__(self, server_rtsp_url: str):
        self.server_rtsp_url = server_rtsp_url.rstrip("/")
        self.relays: Dict[str, StreamRelay] = {}
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        if not shutil.which("ffmpeg"):
            raise RuntimeError(
                "FFmpeg is not installed. Please install it:\\n"
                "  - Windows: choco install ffmpeg\\n"
                "  - macOS: brew install ffmpeg\\n"
                "  - Linux: apt install ffmpeg"
            )
        logger.info("FFmpeg found")
    
    def start_relay(self, camera_id: str, local_rtsp_url: str, stream_key: str = None) -> bool:
        self.stop_relay(camera_id)
        
        stream_path = stream_key or camera_id
        remote_url = f"{self.server_rtsp_url}/{stream_path}"
        
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "warning",
            "-rtsp_transport", "tcp", "-i", local_rtsp_url,
            "-c", "copy", "-f", "rtsp", "-rtsp_transport", "tcp", remote_url
        ]
        
        try:
            logger.info(f"Starting relay for {camera_id}: {local_rtsp_url} -> {remote_url}")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
            
            asyncio.get_event_loop().call_later(2, self._check_process, camera_id)
            
            self.relays[camera_id] = StreamRelay(
                camera_id=camera_id, local_rtsp_url=local_rtsp_url,
                remote_rtsp_url=remote_url, process=process
            )
            logger.info(f"Relay started for {camera_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start relay for {camera_id}: {e}")
            return False
    
    def _check_process(self, camera_id: str):
        relay = self.relays.get(camera_id)
        if relay and not relay.is_running():
            stderr = relay.process.stderr.read().decode() if relay.process.stderr else ""
            logger.error(f"Relay for {camera_id} died: {stderr}")
    
    def stop_relay(self, camera_id: str) -> bool:
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
        for camera_id in list(self.relays.keys()):
            self.stop_relay(camera_id)
    
    def get_status(self) -> Dict[str, bool]:
        return {camera_id: relay.is_running() for camera_id, relay in self.relays.items()}
    
    def restart_dead_relays(self):
        for camera_id, relay in list(self.relays.items()):
            if not relay.is_running():
                logger.warning(f"Relay for {camera_id} died, restarting...")
                self.start_relay(camera_id, relay.local_rtsp_url, camera_id)
''',

    "requirements.txt": '''# Vigila.io Local Agent - Dependencies
httpx>=0.25.0
websockets>=12.0
python-dotenv>=1.0.0
netifaces>=0.11.0
wsdiscovery>=2.0.0
onvif-zeep>=0.2.12
psutil>=5.9.0
''',
}


class DownloadAgentRequest(BaseModel):
    """Request to download agent with pre-configured token."""
    tenant_id: int
    agent_name: str = "vigila-agent"


@router.post("/download")
async def download_agent(
    request: DownloadAgentRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate and download the agent package with pre-configured token.
    
    Creates a ZIP file containing:
    - All agent Python files
    - Pre-configured .env file with token
    - README with instructions
    """
    # Verify tenant exists
    result = await db.execute(select(Tenant).filter(Tenant.id == request.tenant_id))
    tenant = result.scalars().first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Generate token
    secret = secrets.token_urlsafe(32)
    token = f"{request.tenant_id}:{secret}"
    
    # Get server URL from environment
    server_url = os.getenv("PUBLIC_API_URL", os.getenv("API_URL", "http://localhost:8000"))
    
    # Create .env content
    env_content = f'''# Vigila.io Local Agent Configuration
# Generated for: {tenant.name}
# Date: {datetime.utcnow().isoformat()}

# Token for authentication (DO NOT SHARE)
VIGILA_TOKEN={token}

# Server URL
VIGILA_SERVER_URL={server_url}

# Agent name (change this to identify your agent)
AGENT_NAME={request.agent_name}

# Optional: Network range to scan (auto-detected if not set)
# NETWORK_RANGE=192.168.1.0/24

# Optional: Heartbeat interval in seconds (default: 30)
# HEARTBEAT_INTERVAL=30

# Optional: Log level (DEBUG, INFO, WARNING, ERROR)
# LOG_LEVEL=INFO
'''

    # Create README content
    readme_content = f'''# Vigila.io Local Agent

Agent pre-configurado para: **{tenant.name}**

## Requisitos

- Python 3.9 o superior
- FFmpeg instalado en el sistema:
  - Windows: `choco install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `apt install ffmpeg`

## Instalación

1. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

2. (Opcional) Edita `.env` para cambiar el nombre del agente o configurar el rango de red.

3. Ejecuta el agente:
   ```bash
   python agent.py
   ```

## Qué hace el agente

1. Se registra automáticamente con el servidor de Vigila.io
2. Descubre cámaras en tu red local (ONVIF/WS-Discovery)
3. Reporta las cámaras encontradas al servidor
4. Espera comandos para relayar streams de cámaras específicas

## Ejecución como servicio

### Linux (systemd)

```bash
sudo nano /etc/systemd/system/vigila-agent.service
```

```ini
[Unit]
Description=Vigila.io Local Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/agent
ExecStart=/usr/bin/python3 agent.py
Restart=always
User=yourusername

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable vigila-agent
sudo systemctl start vigila-agent
```

### Windows

Usa NSSM o Task Scheduler para ejecutar el agente al inicio.

## Solución de problemas

- **Error de conexión**: Verifica que `VIGILA_SERVER_URL` sea correcto
- **FFmpeg no encontrado**: Instala FFmpeg y reinicia la terminal
- **No se descubren cámaras**: Configura `NETWORK_RANGE` manualmente

---
Generado por Vigila.io - {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC
'''

    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add Python files
        for filename, content in AGENT_FILES.items():
            zf.writestr(f"vigila-agent/{filename}", content)
        
        # Add .env file with token
        zf.writestr("vigila-agent/.env", env_content)
        
        # Add README
        zf.writestr("vigila-agent/README.md", readme_content)
    
    zip_buffer.seek(0)
    
    # Return as download
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=vigila-agent-{tenant.slug}.zip"
        }
    )
