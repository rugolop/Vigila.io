"""
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
    """
    Discover cameras using WS-Discovery (ONVIF).
    """
    cameras = []
    
    try:
        from wsdiscovery.discovery import ThreadedWSDiscovery
        from wsdiscovery import QName
        
        wsd = ThreadedWSDiscovery()
        wsd.start()
        
        # Search for ONVIF devices
        # Use proper QName objects for WS-Discovery types
        onvif_ns = "http://www.onvif.org/ver10/network/wsdl"
        services = wsd.searchServices(
            types=[QName(onvif_ns, "NetworkVideoTransmitter")],
            timeout=timeout
        )
        
        for service in services:
            try:
                # Extract IP from XAddrs
                xaddrs = service.getXAddrs()
                if xaddrs:
                    for addr in xaddrs:
                        # Parse URL to get IP
                        import re
                        match = re.search(r'//([^:/]+)', addr)
                        if match:
                            ip = match.group(1)
                            # Default ONVIF port is 80
                            port = 80
                            port_match = re.search(r':(\d+)', addr)
                            if port_match:
                                port = int(port_match.group(1))
                            
                            camera = DiscoveredCamera(
                                ip=ip,
                                port=port,
                                onvif_url=addr,
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
    """
    Scan common RTSP ports in the network.
    """
    cameras = []
    common_ports = [554, 8554, 80, 8080]
    
    if network_range is None:
        network_range = get_network_range()
    
    # Parse network range
    base_ip = network_range.split("/")[0]
    base_parts = base_ip.split(".")[:3]
    
    async def check_port(ip: str, port: int) -> Optional[DiscoveredCamera]:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return DiscoveredCamera(ip=ip, port=port)
        except:
            return None
    
    # Scan IPs 1-254
    tasks = []
    for i in range(1, 255):
        ip = f"{base_parts[0]}.{base_parts[1]}.{base_parts[2]}.{i}"
        for port in common_ports:
            tasks.append(check_port(ip, port))
    
    logger.info(f"Scanning {network_range} for cameras...")
    results = await asyncio.gather(*tasks)
    
    # Filter found devices
    found_ips = set()
    for result in results:
        if result and result.ip not in found_ips:
            cameras.append(result)
            found_ips.add(result.ip)
            logger.info(f"Found potential camera at {result.ip}:{result.port}")
    
    return cameras


async def discover_cameras(network_range: str = None, timeout: int = 5) -> List[DiscoveredCamera]:
    """
    Discover cameras using multiple methods.
    """
    all_cameras = []
    seen_ips = set()
    
    # Method 1: ONVIF/WS-Discovery
    logger.info("Starting ONVIF discovery...")
    onvif_cameras = await discover_onvif_cameras(timeout=timeout)
    for cam in onvif_cameras:
        if cam.ip not in seen_ips:
            all_cameras.append(cam)
            seen_ips.add(cam.ip)
    
    # Method 2: Port scanning (if ONVIF found nothing)
    if not all_cameras:
        logger.info("No ONVIF cameras found, scanning common ports...")
        port_cameras = await scan_common_ports(network_range, timeout=0.3)
        for cam in port_cameras:
            if cam.ip not in seen_ips:
                all_cameras.append(cam)
                seen_ips.add(cam.ip)
    
    logger.info(f"Total cameras discovered: {len(all_cameras)}")
    return all_cameras
