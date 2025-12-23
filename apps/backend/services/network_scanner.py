"""
Network scanner for discovering IP cameras.
Uses ONVIF WS-Discovery and port scanning to find cameras on the local network.
"""

import asyncio
import socket
import struct
import re
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import ipaddress


@dataclass
class DiscoveredCamera:
    """Represents a discovered camera on the network."""
    ip: str
    port: int = 554
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    name: Optional[str] = None
    onvif_port: Optional[int] = None
    rtsp_urls: List[str] = None
    discovery_method: str = "port_scan"
    
    def __post_init__(self):
        if self.rtsp_urls is None:
            self.rtsp_urls = []
    
    def to_dict(self) -> dict:
        return asdict(self)


# Common RTSP paths for different camera manufacturers
COMMON_RTSP_PATHS = {
    "generic": [
        "/live/ch00_0",
        "/live/ch00_1",
        "/stream1",
        "/stream2",
        "/h264",
        "/h264_stream",
        "/video1",
        "/video.h264",
        "/cam/realmonitor?channel=1&subtype=0",
        "/cam/realmonitor?channel=1&subtype=1",
        "/Streaming/Channels/101",
        "/Streaming/Channels/102",
    ],
    "hikvision": [
        "/Streaming/Channels/101",  # Main stream
        "/Streaming/Channels/102",  # Sub stream
        "/ISAPI/streaming/channels/101",
    ],
    "dahua": [
        "/cam/realmonitor?channel=1&subtype=0",  # Main stream
        "/cam/realmonitor?channel=1&subtype=1",  # Sub stream
    ],
    "axis": [
        "/axis-media/media.amp",
        "/mjpg/video.mjpg",
    ],
    "foscam": [
        "/videoMain",
        "/videoSub",
    ],
    "reolink": [
        "/h264Preview_01_main",
        "/h264Preview_01_sub",
    ],
    "amcrest": [
        "/cam/realmonitor?channel=1&subtype=0",
        "/cam/realmonitor?channel=1&subtype=1",
    ],
    "uniview": [
        "/media/video1",
        "/media/video2",
    ],
}

# ONVIF WS-Discovery message
WS_DISCOVERY_MESSAGE = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing" 
               xmlns:tns="http://schemas.xmlsoap.org/ws/2005/04/discovery">
    <soap:Header>
        <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>
        <wsa:MessageID>urn:uuid:c032cfdd-c3ca-49dc-820e-ee6696ad63e2</wsa:MessageID>
        <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
    </soap:Header>
    <soap:Body>
        <tns:Probe>
            <tns:Types>tns:NetworkVideoTransmitter</tns:Types>
        </tns:Probe>
    </soap:Body>
</soap:Envelope>"""


def get_local_network_range() -> Optional[str]:
    """
    Get the local network IP range (e.g., '192.168.1.0/24').
    """
    try:
        # Create a socket to find the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Assume /24 network (most common for home/small office)
        ip_parts = local_ip.split('.')
        network = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
        return network
    except Exception as e:
        print(f"Error getting local network: {e}")
        return None


def check_port(ip: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is open on the given IP."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False


def scan_ip_for_camera(ip: str, timeout: float = 1.0) -> Optional[DiscoveredCamera]:
    """
    Scan a single IP for camera services (RTSP port 554, HTTP ports 80/8080).
    """
    rtsp_ports = [554, 8554]
    http_ports = [80, 8080, 8000]
    
    camera = None
    
    # Check RTSP ports
    for port in rtsp_ports:
        if check_port(ip, port, timeout):
            camera = DiscoveredCamera(
                ip=ip,
                port=port,
                discovery_method="port_scan",
                rtsp_urls=[f"rtsp://{ip}:{port}{path}" for path in COMMON_RTSP_PATHS["generic"][:4]]
            )
            break
    
    # If camera found, also check for ONVIF/HTTP
    if camera:
        for port in http_ports:
            if check_port(ip, port, timeout):
                camera.onvif_port = port
                break
    
    return camera


async def scan_network_ports(network_range: str = None, timeout: float = 0.5, max_workers: int = 50) -> List[DiscoveredCamera]:
    """
    Scan the local network for devices with RTSP ports open.
    
    Args:
        network_range: IP range to scan (e.g., '192.168.1.0/24'). Auto-detected if None.
        timeout: Connection timeout per host
        max_workers: Maximum concurrent connections
    
    Returns:
        List of discovered cameras
    """
    if network_range is None:
        network_range = get_local_network_range()
        if network_range is None:
            return []
    
    print(f"Scanning network: {network_range}")
    
    try:
        network = ipaddress.ip_network(network_range, strict=False)
        hosts = [str(ip) for ip in network.hosts()]
    except ValueError as e:
        print(f"Invalid network range: {e}")
        return []
    
    cameras = []
    
    # Use thread pool for concurrent scanning
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create tasks for all hosts
        tasks = [
            loop.run_in_executor(executor, scan_ip_for_camera, ip, timeout)
            for ip in hosts
        ]
        
        # Wait for all tasks
        results = await asyncio.gather(*tasks)
        
        # Collect found cameras
        for result in results:
            if result is not None:
                cameras.append(result)
    
    print(f"Found {len(cameras)} potential cameras")
    return cameras


async def discover_onvif_cameras(timeout: float = 3.0) -> List[DiscoveredCamera]:
    """
    Discover cameras using ONVIF WS-Discovery protocol.
    This uses UDP multicast to find ONVIF-compatible devices.
    
    Returns:
        List of discovered ONVIF cameras
    """
    cameras = []
    
    # WS-Discovery multicast address and port
    MULTICAST_IP = "239.255.255.250"
    MULTICAST_PORT = 3702
    
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        
        # Send discovery message
        sock.sendto(WS_DISCOVERY_MESSAGE.encode(), (MULTICAST_IP, MULTICAST_PORT))
        
        print("Sent ONVIF WS-Discovery probe, waiting for responses...")
        
        # Collect responses
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                data, addr = sock.recvfrom(65535)
                response = data.decode('utf-8', errors='ignore')
                
                # Parse the response to extract device info
                camera = parse_onvif_response(response, addr[0])
                if camera:
                    # Check if we already have this IP
                    if not any(c.ip == camera.ip for c in cameras):
                        cameras.append(camera)
                        print(f"Found ONVIF device: {camera.ip}")
            except socket.timeout:
                break
            except Exception as e:
                print(f"Error receiving response: {e}")
                continue
        
        sock.close()
        
    except Exception as e:
        print(f"ONVIF discovery error: {e}")
    
    return cameras


def parse_onvif_response(response: str, ip: str) -> Optional[DiscoveredCamera]:
    """
    Parse ONVIF WS-Discovery response to extract camera information.
    """
    try:
        # Extract XAddrs (service addresses)
        xaddrs_match = re.search(r'<[^>]*XAddrs[^>]*>([^<]+)</[^>]*XAddrs>', response)
        
        # Extract Scopes (device info)
        scopes_match = re.search(r'<[^>]*Scopes[^>]*>([^<]+)</[^>]*Scopes>', response)
        
        manufacturer = None
        model = None
        name = None
        onvif_port = 80
        
        if scopes_match:
            scopes = scopes_match.group(1)
            
            # Parse manufacturer
            mfr_match = re.search(r'onvif://www\.onvif\.org/hardware/([^\s]+)', scopes)
            if mfr_match:
                model = mfr_match.group(1)
            
            # Parse name
            name_match = re.search(r'onvif://www\.onvif\.org/name/([^\s]+)', scopes)
            if name_match:
                name = name_match.group(1).replace('%20', ' ')
            
            # Try to detect manufacturer from scopes
            scopes_lower = scopes.lower()
            if 'hikvision' in scopes_lower:
                manufacturer = 'Hikvision'
            elif 'dahua' in scopes_lower:
                manufacturer = 'Dahua'
            elif 'axis' in scopes_lower:
                manufacturer = 'Axis'
            elif 'reolink' in scopes_lower:
                manufacturer = 'Reolink'
            elif 'amcrest' in scopes_lower:
                manufacturer = 'Amcrest'
            elif 'uniview' in scopes_lower or 'unv' in scopes_lower:
                manufacturer = 'Uniview'
        
        if xaddrs_match:
            xaddrs = xaddrs_match.group(1)
            # Extract port from XAddrs URL
            port_match = re.search(r':(\d+)/', xaddrs)
            if port_match:
                onvif_port = int(port_match.group(1))
        
        # Generate likely RTSP URLs based on manufacturer
        rtsp_urls = []
        if manufacturer and manufacturer.lower() in COMMON_RTSP_PATHS:
            paths = COMMON_RTSP_PATHS[manufacturer.lower()]
        else:
            paths = COMMON_RTSP_PATHS["generic"][:6]
        
        for path in paths:
            rtsp_urls.append(f"rtsp://{ip}:554{path}")
        
        return DiscoveredCamera(
            ip=ip,
            port=554,
            manufacturer=manufacturer,
            model=model,
            name=name or f"Camera-{ip.split('.')[-1]}",
            onvif_port=onvif_port,
            rtsp_urls=rtsp_urls,
            discovery_method="onvif"
        )
        
    except Exception as e:
        print(f"Error parsing ONVIF response: {e}")
        return None


async def discover_cameras(
    use_onvif: bool = True,
    use_port_scan: bool = True,
    network_range: str = None,
    scan_timeout: float = 0.5,
    onvif_timeout: float = 3.0
) -> List[DiscoveredCamera]:
    """
    Discover cameras on the network using multiple methods.
    
    Args:
        use_onvif: Use ONVIF WS-Discovery
        use_port_scan: Use port scanning
        network_range: Network range for port scan (auto-detected if None)
        scan_timeout: Timeout for port scan per host
        onvif_timeout: Timeout for ONVIF discovery
    
    Returns:
        Combined list of discovered cameras (deduplicated by IP)
    """
    all_cameras: Dict[str, DiscoveredCamera] = {}
    
    # Run discovery methods
    tasks = []
    
    if use_onvif:
        tasks.append(discover_onvif_cameras(onvif_timeout))
    
    if use_port_scan:
        tasks.append(scan_network_ports(network_range, scan_timeout))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Merge results, preferring ONVIF info
    for result in results:
        if isinstance(result, Exception):
            print(f"Discovery error: {result}")
            continue
            
        for camera in result:
            if camera.ip in all_cameras:
                # Merge info, prefer ONVIF data
                existing = all_cameras[camera.ip]
                if camera.discovery_method == "onvif":
                    camera.rtsp_urls = list(set(camera.rtsp_urls + existing.rtsp_urls))
                    all_cameras[camera.ip] = camera
                else:
                    existing.rtsp_urls = list(set(existing.rtsp_urls + camera.rtsp_urls))
            else:
                all_cameras[camera.ip] = camera
    
    return list(all_cameras.values())


# Utility function to test if an RTSP URL is valid
async def test_rtsp_url(url: str, timeout: float = 5.0) -> bool:
    """
    Test if an RTSP URL is accessible.
    Note: This is a basic check, doesn't verify authentication.
    """
    try:
        # Parse URL to get host and port
        match = re.match(r'rtsp://(?:[^:@]+(?::[^@]+)?@)?([^:/]+)(?::(\d+))?', url)
        if not match:
            return False
        
        host = match.group(1)
        port = int(match.group(2)) if match.group(2) else 554
        
        return check_port(host, port, timeout)
    except:
        return False
