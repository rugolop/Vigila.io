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
    If an agent with the same name, tenant, and local_ip already exists, reuse its ID.
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
    
    # Check if agent already exists with same name, tenant, and local_ip
    existing_agent_id = None
    for aid, info in active_agents.items():
        if (info["name"] == request.name and 
            info["tenant_id"] == tenant_id and 
            info["local_ip"] == request.local_ip):
            existing_agent_id = aid
            break
    
    # Reuse existing agent_id or generate new one
    agent_id = existing_agent_id if existing_agent_id else generate_agent_id()
    
    # Store/update agent info
    active_agents[agent_id] = {
        "name": request.name,
        "tenant_id": tenant_id,
        "tenant_slug": tenant.slug,
        "local_ip": request.local_ip,
        "version": request.version,
        "registered_at": active_agents.get(agent_id, {}).get("registered_at", datetime.utcnow().isoformat()),
        "last_seen": datetime.utcnow().isoformat(),
        "token_hash": hash(request.token)
    }
    
    # Initialize pending commands if new agent
    if agent_id not in pending_commands:
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


@router.get("")
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
            "cameras_count": info.get("cameras_count", 0),
            "discovered_cameras_count": len(discovered_cameras_cache.get(agent_id, []))
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

    "install.sh": '''#!/bin/bash
#
# Vigila.io Local Agent - Instalador para Linux/macOS
# Este script configura automáticamente el agente
#

set -e

echo "========================================"
echo "  Vigila.io Agent - Instalador"
echo "========================================"
echo ""

# Colores para output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Detectar sistema operativo
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    *)          MACHINE="UNKNOWN"
esac

echo "Sistema detectado: $MACHINE"
echo ""

# Verificar Python
echo "Verificando Python..."
if command -v python3 &> /dev/null; then
    PYTHON=python3
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ Python $PYTHON_VERSION encontrado${NC}"
else
    echo -e "${RED}✗ Python 3 no encontrado${NC}"
    echo "Por favor instala Python 3.9 o superior:"
    if [ "$MACHINE" = "Mac" ]; then
        echo "  brew install python3"
    else
        echo "  sudo apt install python3 python3-pip python3-venv"
    fi
    exit 1
fi

# Verificar versión de Python >= 3.9
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    echo -e "${RED}✗ Se requiere Python 3.9 o superior (tienes $PYTHON_VERSION)${NC}"
    exit 1
fi

# Instalar FFmpeg si no está
echo ""
echo "Verificando FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -n1 | awk '{print $3}')
    echo -e "${GREEN}✓ FFmpeg $FFMPEG_VERSION encontrado${NC}"
else
    echo -e "${YELLOW}FFmpeg no encontrado, instalando...${NC}"
    if [ "$MACHINE" = "Mac" ]; then
        if command -v brew &> /dev/null; then
            brew install ffmpeg
        else
            echo -e "${RED}Homebrew no encontrado. Instala FFmpeg manualmente.${NC}"
            exit 1
        fi
    else
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y ffmpeg
        elif command -v yum &> /dev/null; then
            sudo yum install -y ffmpeg
        elif command -v pacman &> /dev/null; then
            sudo pacman -S ffmpeg
        else
            echo -e "${RED}No se pudo instalar FFmpeg automáticamente.${NC}"
            exit 1
        fi
    fi
    echo -e "${GREEN}✓ FFmpeg instalado${NC}"
fi

# Crear entorno virtual
echo ""
echo "Creando entorno virtual..."
if [ -d "venv" ]; then
    echo -e "${YELLOW}Entorno virtual existente encontrado, usando...${NC}"
else
    $PYTHON -m venv venv
    echo -e "${GREEN}✓ Entorno virtual creado${NC}"
fi

# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias
echo ""
echo "Instalando dependencias..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencias instaladas${NC}"

# Verificar archivo .env
echo ""
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ Archivo .env encontrado${NC}"
else
    echo -e "${RED}✗ Archivo .env no encontrado${NC}"
    exit 1
fi

# Preguntar si crear servicio systemd
echo ""
echo "========================================"
echo "  Configuración del Servicio"
echo "========================================"
echo ""

if [ "$MACHINE" = "Linux" ] && command -v systemctl &> /dev/null; then
    read -p "¿Deseas instalar el agente como servicio systemd? (s/n): " INSTALL_SERVICE
    if [ "$INSTALL_SERVICE" = "s" ] || [ "$INSTALL_SERVICE" = "S" ]; then
        CURRENT_DIR=$(pwd)
        CURRENT_USER=$(whoami)
        
        # Crear archivo de servicio
        sudo tee /etc/systemd/system/vigila-agent.service > /dev/null << EOF
[Unit]
Description=Vigila.io Local Agent
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python agent.py
Restart=always
RestartSec=10
Environment=PATH=$CURRENT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF
        
        # Habilitar e iniciar servicio
        sudo systemctl daemon-reload
        sudo systemctl enable vigila-agent
        sudo systemctl start vigila-agent
        
        echo -e "${GREEN}✓ Servicio instalado y ejecutándose${NC}"
        echo ""
        echo "Comandos útiles:"
        echo "  sudo systemctl status vigila-agent   # Ver estado"
        echo "  sudo systemctl restart vigila-agent  # Reiniciar"
        echo "  sudo journalctl -u vigila-agent -f   # Ver logs"
    else
        echo ""
        echo "Para ejecutar manualmente:"
        echo "  source venv/bin/activate"
        echo "  python agent.py"
    fi
else
    echo "Para ejecutar manualmente:"
    echo "  source venv/bin/activate"
    echo "  python agent.py"
fi

echo ""
echo "========================================"
echo -e "${GREEN}  ¡Instalación completada!${NC}"
echo "========================================"
echo ""
''',

    "install.bat": '''@echo off
REM
REM Vigila.io Local Agent - Instalador para Windows
REM Este script configura automaticamente el agente
REM

echo ========================================
echo   Vigila.io Agent - Instalador Windows
echo ========================================
echo.

REM Verificar Python
echo Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado
    echo Por favor instala Python 3.9 o superior desde https://python.org
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion
    pause
    exit /b 1
)
python --version
echo [OK] Python encontrado
echo.

REM Verificar FFmpeg
echo Verificando FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] FFmpeg no encontrado
    echo.
    echo Para instalar FFmpeg:
    echo   1. Descarga desde https://ffmpeg.org/download.html
    echo   2. Extrae y agrega la carpeta bin a tu PATH
    echo   3. O usa: choco install ffmpeg (si tienes Chocolatey)
    echo.
    set /p CONTINUE="Deseas continuar sin FFmpeg? (s/n): "
    if /i not "%CONTINUE%"=="s" exit /b 1
) else (
    echo [OK] FFmpeg encontrado
)
echo.

REM Crear entorno virtual
echo Creando entorno virtual...
if exist venv (
    echo Entorno virtual existente encontrado, usando...
) else (
    python -m venv venv
    echo [OK] Entorno virtual creado
)

REM Activar entorno virtual
call venv\\Scripts\\activate.bat

REM Instalar dependencias
echo.
echo Instalando dependencias...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
echo [OK] Dependencias instaladas
echo.

REM Verificar archivo .env
if exist .env (
    echo [OK] Archivo .env encontrado
) else (
    echo [ERROR] Archivo .env no encontrado
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Configuracion del Servicio
echo ========================================
echo.

set /p INSTALL_SERVICE="Deseas crear una tarea programada para iniciar con Windows? (s/n): "
if /i "%INSTALL_SERVICE%"=="s" (
    REM Crear script de inicio
    echo @echo off > start_agent.bat
    echo cd /d "%CD%" >> start_agent.bat
    echo call venv\\Scripts\\activate.bat >> start_agent.bat
    echo python agent.py >> start_agent.bat
    
    REM Crear tarea programada
    schtasks /create /tn "VigilaAgent" /tr "\"%CD%\\start_agent.bat\"" /sc onlogon /rl highest /f >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se pudo crear la tarea programada
        echo Ejecuta este script como Administrador
    ) else (
        echo [OK] Tarea programada creada
        echo El agente se iniciara automaticamente al iniciar sesion
    )
)

echo.
echo ========================================
echo   Para ejecutar el agente ahora:
echo ========================================
echo   venv\\Scripts\\activate
echo   python agent.py
echo.
echo ========================================
echo   Instalacion completada!
echo ========================================
echo.
pause
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

Agente pre-configurado para: **{tenant.name}**

## 🚀 Instalación Rápida

### Linux / macOS
```bash
chmod +x install.sh
./install.sh
```

### Windows (PowerShell como Administrador)
```powershell
.\\install.bat
```

El script de instalación:
- ✅ Verifica que Python 3.9+ esté instalado
- ✅ Instala FFmpeg si no está disponible (Linux/macOS)
- ✅ Crea un entorno virtual de Python
- ✅ Instala todas las dependencias
- ✅ Opcionalmente configura el agente como servicio del sistema

---

## 📋 Requisitos del Sistema

| Requisito | Versión Mínima | Notas |
|-----------|----------------|-------|
| Python | 3.9+ | [Descargar](https://python.org) |
| FFmpeg | Cualquiera | Se instala automáticamente en Linux |
| Red | - | Acceso a la red local de las cámaras |

### Instalar FFmpeg manualmente:
- **Windows**: `choco install ffmpeg` o [descargar](https://ffmpeg.org/download.html)
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

---

## 🛠 Instalación Manual

Si prefieres no usar el script de instalación:

```bash
# 1. Crear entorno virtual
python3 -m venv venv

# 2. Activar entorno virtual
source venv/bin/activate  # Linux/macOS
venv\\Scripts\\activate     # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar agente
python agent.py
```

---

## ⚙️ Configuración

Edita el archivo `.env` para personalizar:

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `AGENT_NAME` | Nombre del agente en el dashboard | `{request.agent_name}` |
| `NETWORK_RANGE` | Rango de red a escanear | Auto-detectado |
| `HEARTBEAT_INTERVAL` | Intervalo de heartbeat (segundos) | 30 |
| `LOG_LEVEL` | Nivel de logging | INFO |

---

## 🔧 Ejecutar como Servicio

### Linux (systemd)

El script `install.sh` puede configurarlo automáticamente. Comandos útiles:

```bash
sudo systemctl status vigila-agent   # Ver estado
sudo systemctl restart vigila-agent  # Reiniciar
sudo systemctl stop vigila-agent     # Detener
sudo journalctl -u vigila-agent -f   # Ver logs en tiempo real
```

### Windows

El script `install.bat` crea una tarea programada. También puedes:
1. Usar NSSM: `nssm install VigilaAgent python.exe agent.py`
2. Crear una tarea en el Programador de Tareas

---

## 📡 Qué hace el agente

1. **Registro**: Se conecta al servidor de Vigila.io y se registra
2. **Descubrimiento**: Busca cámaras en tu red local (ONVIF/WS-Discovery)
3. **Reporte**: Envía la lista de cámaras encontradas al servidor
4. **Relay**: Retransmite streams de cámaras seleccionadas al servidor

---

## 🔍 Solución de Problemas

| Problema | Solución |
|----------|----------|
| Error de conexión | Verifica `VIGILA_SERVER_URL` en `.env` |
| FFmpeg no encontrado | Instala FFmpeg y reinicia la terminal |
| No se descubren cámaras | Configura `NETWORK_RANGE` manualmente |
| Agente se desconecta | Revisa los logs con `journalctl` o en consola |

---

*Generado por Vigila.io - {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC*
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
