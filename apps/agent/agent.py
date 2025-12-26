#!/usr/bin/env python3
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
    Copy .env.example to .env and configure your settings.
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
    """
    Main agent class that coordinates all operations.
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent_id: Optional[str] = None
        self.registered = False
        self.running = False
        self.discovered_cameras: List[DiscoveredCamera] = []
        self.active_cameras: Dict[str, dict] = {}  # camera_id -> camera_info
        self.relay_manager: Optional[StreamRelayManager] = None
        
        # Set log level
        logging.getLogger().setLevel(config.log_level)
    
    async def register(self) -> bool:
        """
        Register this agent with the Vigila.io server.
        """
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
                    
                    # Get RTSP server URL from response
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
        """
        Send periodic heartbeat to the server.
        """
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
                        # Process any commands from server
                        await self.process_commands(data.get("commands", []))
                    else:
                        logger.warning(f"Heartbeat failed: {response.status_code}")
                        
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            await asyncio.sleep(self.config.heartbeat_interval)
    
    async def process_commands(self, commands: List[dict]):
        """
        Process commands received from the server.
        """
        for cmd in commands:
            cmd_type = cmd.get("type")
            
            if cmd_type == "discover":
                # Server requests camera discovery
                await self.discover_and_report()
                
            elif cmd_type == "start_relay":
                # Start relaying a specific camera
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
                # Stop relaying a camera
                camera_id = cmd.get("camera_id")
                if camera_id:
                    self.relay_manager.stop_relay(camera_id)
                    self.active_cameras.pop(camera_id, None)
                    
            elif cmd_type == "restart_relay":
                # Restart a relay
                camera_id = cmd.get("camera_id")
                if camera_id and camera_id in self.active_cameras:
                    info = self.active_cameras[camera_id]
                    self.relay_manager.stop_relay(camera_id)
                    self.relay_manager.start_relay(
                        camera_id, 
                        info["rtsp_url"], 
                        info.get("stream_key")
                    )
    
    async def discover_and_report(self):
        """
        Discover cameras and report to the server.
        """
        logger.info("Starting camera discovery...")
        
        self.discovered_cameras = await discover_cameras(
            network_range=self.config.network_range
        )
        
        # Report to server
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
                    json={
                        "token": self.config.token,
                        "cameras": cameras_data
                    },
                    timeout=30.0
                )
                
                logger.info(f"Reported {len(cameras_data)} discovered cameras to server")
                
        except Exception as e:
            logger.error(f"Failed to report cameras: {e}")
    
    async def monitor_relays(self):
        """
        Monitor and restart dead relays.
        """
        while self.running:
            if self.relay_manager:
                self.relay_manager.restart_dead_relays()
            await asyncio.sleep(10)  # Check every 10 seconds
    
    async def run(self):
        """
        Main run loop.
        """
        logger.info("=" * 50)
        logger.info("Vigila.io Local Agent Starting")
        logger.info(f"Agent Name: {self.config.agent_name}")
        logger.info(f"Server: {self.config.server_url}")
        logger.info(f"Local IP: {get_local_ip()}")
        logger.info("=" * 50)
        
        # Register with server
        if not await self.register():
            logger.error("Failed to register with server. Exiting.")
            return
        
        self.running = True
        
        # Initial camera discovery
        await self.discover_and_report()
        
        # Start background tasks
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
        """
        Cleanup on shutdown.
        """
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
    
    # Handle signals
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        agent.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run agent
    asyncio.run(agent.run())


if __name__ == "__main__":
    main()
