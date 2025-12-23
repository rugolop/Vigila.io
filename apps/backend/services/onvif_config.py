"""
ONVIF Camera Configuration Service

This service provides functionality to configure IP cameras via ONVIF protocol.
It allows reading and modifying video encoder settings like resolution, bitrate, codec, and FPS.
"""

import asyncio
import hashlib
import base64
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from xml.etree import ElementTree as ET
import aiohttp


# ONVIF Namespaces
NAMESPACES = {
    'soap': 'http://www.w3.org/2003/05/soap-envelope',
    'wsse': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
    'wsu': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
    'trt': 'http://www.onvif.org/ver10/media/wsdl',
    'tt': 'http://www.onvif.org/ver10/schema',
    'tds': 'http://www.onvif.org/ver10/device/wsdl',
}


@dataclass
class VideoResolution:
    width: int
    height: int
    
    def __str__(self):
        return f"{self.width}x{self.height}"


@dataclass
class VideoEncoderConfig:
    """Video encoder configuration from ONVIF camera"""
    token: str
    name: str
    encoding: str  # H264, H265, JPEG, MPEG4
    resolution: VideoResolution
    quality: float  # 0-100
    framerate_limit: int
    bitrate_limit: int  # kbps
    gov_length: int  # GOP size / keyframe interval
    profile: Optional[str] = None  # Baseline, Main, High, etc.
    use_count: int = 0


@dataclass
class MediaProfile:
    """ONVIF Media Profile"""
    token: str
    name: str
    video_source_token: Optional[str] = None
    video_encoder_token: Optional[str] = None
    audio_source_token: Optional[str] = None
    audio_encoder_token: Optional[str] = None
    

@dataclass
class VideoEncoderOptions:
    """Available options for video encoder configuration"""
    encoding_options: List[str]  # H264, H265, etc.
    resolution_options: List[VideoResolution]
    quality_range: tuple  # (min, max)
    framerate_range: tuple  # (min, max)
    bitrate_range: tuple  # (min, max) in kbps
    gov_length_range: tuple  # (min, max)
    h264_profiles: List[str]  # Baseline, Main, High
    h265_profiles: List[str]


def create_wsse_header(username: str, password: str) -> str:
    """
    Create WS-Security UsernameToken header for ONVIF authentication.
    Uses Password Digest authentication.
    """
    # Create nonce (random bytes)
    nonce = os.urandom(16)
    nonce_b64 = base64.b64encode(nonce).decode('utf-8')
    
    # Create timestamp
    created = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    # Create password digest: Base64(SHA1(nonce + created + password))
    digest_input = nonce + created.encode('utf-8') + password.encode('utf-8')
    password_digest = base64.b64encode(hashlib.sha1(digest_input).digest()).decode('utf-8')
    
    return f'''
    <wsse:Security soap:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
        <wsse:UsernameToken>
            <wsse:Username>{username}</wsse:Username>
            <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{password_digest}</wsse:Password>
            <wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce_b64}</wsse:Nonce>
            <wsu:Created>{created}</wsu:Created>
        </wsse:UsernameToken>
    </wsse:Security>
    '''


def create_soap_envelope(body: str, username: str = None, password: str = None, namespace_prefix: str = "trt") -> str:
    """Create SOAP envelope with optional WS-Security header"""
    header = ""
    if username and password:
        header = f"<soap:Header>{create_wsse_header(username, password)}</soap:Header>"
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
               xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
               xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
               xmlns:tt="http://www.onvif.org/ver10/schema">
    {header}
    <soap:Body>
        {body}
    </soap:Body>
</soap:Envelope>'''


class ONVIFClient:
    """ONVIF client for camera configuration"""
    
    def __init__(self, host: str, port: int = 80, username: str = None, password: str = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.device_service_url = f"http://{host}:{port}/onvif/device_service"
        self.media_service_url = None  # Will be discovered
        self._capabilities_loaded = False
        
    async def _send_request(self, url: str, body: str, namespace_prefix: str = "trt") -> Optional[ET.Element]:
        """Send SOAP request and return parsed XML response"""
        envelope = create_soap_envelope(body, self.username, self.password, namespace_prefix)
        
        headers = {
            'Content-Type': 'application/soap+xml; charset=utf-8',
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=envelope, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        text = await response.text()
                        # Register namespaces for parsing
                        for prefix, uri in NAMESPACES.items():
                            ET.register_namespace(prefix, uri)
                        return ET.fromstring(text)
                    else:
                        print(f"ONVIF request failed: {response.status}")
                        error_text = await response.text()
                        print(f"Error: {error_text[:500]}")
                        return None
        except asyncio.TimeoutError:
            print(f"ONVIF request timeout to {url}")
            return None
        except Exception as e:
            print(f"ONVIF request error: {e}")
            return None
    
    async def get_capabilities(self) -> bool:
        """Get device capabilities to discover service URLs"""
        if self._capabilities_loaded and self.media_service_url:
            return True
            
        body = '<tds:GetCapabilities><tds:Category>All</tds:Category></tds:GetCapabilities>'
        
        response = await self._send_request(self.device_service_url, body, "tds")
        if response is None:
            # Try alternate path
            self.device_service_url = f"http://{self.host}:{self.port}/onvif/device"
            response = await self._send_request(self.device_service_url, body, "tds")
            
        if response is None:
            # Try without path
            self.device_service_url = f"http://{self.host}:{self.port}/"
            response = await self._send_request(self.device_service_url, body, "tds")
        
        if response is None:
            # Fallback to standard paths
            self.media_service_url = f"http://{self.host}:{self.port}/onvif/media"
            return False
        
        # Parse capabilities to find media service URL
        for elem in response.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag == 'Media':
                xaddr = elem.find('.//{http://www.onvif.org/ver10/schema}XAddr')
                if xaddr is not None and xaddr.text:
                    self.media_service_url = xaddr.text
                    print(f"Found Media service URL: {self.media_service_url}")
                    self._capabilities_loaded = True
                    return True
        
        # Check for XAddr directly
        for elem in response.iter():
            if 'XAddr' in elem.tag and elem.text and 'media' in elem.text.lower():
                self.media_service_url = elem.text
                print(f"Found Media service URL (direct): {self.media_service_url}")
                self._capabilities_loaded = True
                return True
        
        # Fallback
        self.media_service_url = f"http://{self.host}:{self.port}/onvif/media"
        return False
    
    async def get_services(self) -> Dict[str, str]:
        """Get device services - alternative method to discover URLs"""
        body = '<tds:GetServices><tds:IncludeCapability>true</tds:IncludeCapability></tds:GetServices>'
        
        response = await self._send_request(self.device_service_url, body, "tds")
        if response is None:
            return {}
        
        services = {}
        for service_elem in response.iter():
            if 'Service' in service_elem.tag:
                namespace = None
                xaddr = None
                
                for child in service_elem.iter():
                    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if tag == 'Namespace' and child.text:
                        namespace = child.text
                    elif tag == 'XAddr' and child.text:
                        xaddr = child.text
                
                if namespace and xaddr:
                    services[namespace] = xaddr
                    if 'media' in namespace.lower():
                        self.media_service_url = xaddr
                        print(f"Found Media service via GetServices: {xaddr}")
        
        return services
    
    async def _ensure_media_url(self):
        """Ensure we have the media service URL"""
        if not self.media_service_url:
            # Try GetCapabilities first
            await self.get_capabilities()
            
            # If still no URL, try GetServices
            if not self.media_service_url:
                await self.get_services()
            
            # Final fallback
            if not self.media_service_url:
                self.media_service_url = f"http://{self.host}:{self.port}/onvif/Media"
    
    async def get_profiles(self) -> List[MediaProfile]:
        """Get all media profiles from the camera"""
        await self._ensure_media_url()
        
        body = '<trt:GetProfiles/>'
        
        response = await self._send_request(self.media_service_url, body)
        if response is None:
            print("GetProfiles: No response received")
            return []
        
        profiles = []
        
        # Debug: print response structure
        print(f"GetProfiles response root tag: {response.tag}")
        
        # Find all Profiles elements - search more broadly
        for elem in response.iter():
            tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag_name == 'Profiles':
                token = elem.get('token', '')
                if not token:
                    # Try to find token attribute with namespace
                    for attr_key in elem.attrib:
                        if 'token' in attr_key.lower():
                            token = elem.attrib[attr_key]
                            break
                
                name = ''
                video_source_token = None
                video_encoder_token = None
                
                for child in elem.iter():
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    
                    if child_tag == 'Name' and child.text:
                        name = child.text
                    elif child_tag == 'VideoSourceConfiguration':
                        video_source_token = child.get('token')
                    elif child_tag == 'VideoEncoderConfiguration':
                        video_encoder_token = child.get('token')
                
                if token:
                    print(f"Found profile: token={token}, name={name}")
                    profiles.append(MediaProfile(
                        token=token,
                        name=name,
                        video_source_token=video_source_token,
                        video_encoder_token=video_encoder_token
                    ))
        
        print(f"GetProfiles: Found {len(profiles)} profiles")
        return profiles
    
    async def get_video_encoder_configurations(self) -> List[VideoEncoderConfig]:
        """Get all video encoder configurations"""
        await self._ensure_media_url()
        
        body = '<trt:GetVideoEncoderConfigurations/>'
        
        response = await self._send_request(self.media_service_url, body)
        if response is None:
            print("GetVideoEncoderConfigurations: No response received")
            return []
        
        configs = []
        
        # Debug: print response structure
        print(f"GetVideoEncoderConfigurations response root tag: {response.tag}")
        
        for elem in response.iter():
            tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            # Look for VideoEncoderConfiguration elements
            if 'VideoEncoderConfiguration' in tag_name or tag_name == 'Configurations':
                token = elem.get('token', '')
                if not token:
                    continue
                
                print(f"Found encoder config element: {tag_name}, token={token}")
                config = self._parse_video_encoder_config(elem, token)
                if config:
                    configs.append(config)
        
        print(f"GetVideoEncoderConfigurations: Found {len(configs)} configs")
        return configs
        
        return configs
    
    async def get_video_encoder_configuration(self, token: str) -> Optional[VideoEncoderConfig]:
        """Get specific video encoder configuration by token"""
        await self._ensure_media_url()
        
        body = f'<trt:GetVideoEncoderConfiguration><trt:ConfigurationToken>{token}</trt:ConfigurationToken></trt:GetVideoEncoderConfiguration>'
        
        response = await self._send_request(self.media_service_url, body)
        if response is None:
            return None
        
        for config_elem in response.iter():
            if 'Configuration' in config_elem.tag and 'VideoEncoder' in config_elem.tag:
                return self._parse_video_encoder_config(config_elem, token)
        
        return None
    
    def _parse_video_encoder_config(self, elem: ET.Element, token: str) -> Optional[VideoEncoderConfig]:
        """Parse video encoder configuration from XML element"""
        try:
            name = ''
            encoding = 'H264'
            width = 1920
            height = 1080
            quality = 50.0
            framerate = 30
            bitrate = 4096
            gov_length = 30
            profile = None
            use_count = 0
            
            for child in elem.iter():
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                
                if tag == 'Name' and child.text:
                    name = child.text
                elif tag == 'UseCount' and child.text:
                    use_count = int(child.text)
                elif tag == 'Encoding' and child.text:
                    encoding = child.text.upper()
                elif tag == 'Width' and child.text:
                    width = int(child.text)
                elif tag == 'Height' and child.text:
                    height = int(child.text)
                elif tag == 'Quality' and child.text:
                    quality = float(child.text)
                elif tag == 'FrameRateLimit' and child.text:
                    framerate = int(child.text)
                elif tag == 'BitrateLimit' and child.text:
                    bitrate = int(child.text)
                elif tag == 'GovLength' and child.text:
                    gov_length = int(child.text)
                elif tag == 'H264Profile' and child.text:
                    profile = child.text
                elif tag == 'H265Profile' and child.text:
                    profile = child.text
            
            return VideoEncoderConfig(
                token=token,
                name=name,
                encoding=encoding,
                resolution=VideoResolution(width, height),
                quality=quality,
                framerate_limit=framerate,
                bitrate_limit=bitrate,
                gov_length=gov_length,
                profile=profile,
                use_count=use_count
            )
        except Exception as e:
            print(f"Error parsing video encoder config: {e}")
            return None
    
    async def get_video_encoder_options(self, profile_token: str = None, config_token: str = None) -> Optional[VideoEncoderOptions]:
        """Get available options for video encoder configuration"""
        await self._ensure_media_url()
        
        if profile_token:
            body = f'<trt:GetVideoEncoderConfigurationOptions><trt:ProfileToken>{profile_token}</trt:ProfileToken></trt:GetVideoEncoderConfigurationOptions>'
        elif config_token:
            body = f'<trt:GetVideoEncoderConfigurationOptions><trt:ConfigurationToken>{config_token}</trt:ConfigurationToken></trt:GetVideoEncoderConfigurationOptions>'
        else:
            body = '<trt:GetVideoEncoderConfigurationOptions/>'
        
        response = await self._send_request(self.media_service_url, body)
        if response is None:
            return None
        
        encoding_options = []
        resolution_options = []
        quality_range = (1, 100)
        framerate_range = (1, 30)
        bitrate_range = (256, 16384)
        gov_length_range = (1, 300)
        h264_profiles = []
        h265_profiles = []
        
        for elem in response.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag == 'H264':
                encoding_options.append('H264')
                for child in elem.iter():
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if child_tag == 'ResolutionsAvailable':
                        w = h = 0
                        for res_child in child:
                            res_tag = res_child.tag.split('}')[-1]
                            if res_tag == 'Width' and res_child.text:
                                w = int(res_child.text)
                            elif res_tag == 'Height' and res_child.text:
                                h = int(res_child.text)
                        if w and h:
                            resolution_options.append(VideoResolution(w, h))
                    elif child_tag == 'H264ProfilesSupported' and child.text:
                        h264_profiles.append(child.text)
                    elif child_tag == 'FrameRateRange':
                        for range_child in child:
                            range_tag = range_child.tag.split('}')[-1]
                            if range_tag == 'Min' and range_child.text:
                                framerate_range = (int(range_child.text), framerate_range[1])
                            elif range_tag == 'Max' and range_child.text:
                                framerate_range = (framerate_range[0], int(range_child.text))
                    elif child_tag == 'GovLengthRange':
                        for range_child in child:
                            range_tag = range_child.tag.split('}')[-1]
                            if range_tag == 'Min' and range_child.text:
                                gov_length_range = (int(range_child.text), gov_length_range[1])
                            elif range_tag == 'Max' and range_child.text:
                                gov_length_range = (gov_length_range[0], int(range_child.text))
            
            elif tag == 'H265':
                encoding_options.append('H265')
                for child in elem.iter():
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if child_tag == 'H265ProfilesSupported' and child.text:
                        h265_profiles.append(child.text)
            
            elif tag == 'JPEG':
                encoding_options.append('JPEG')
            
            elif tag == 'QualityRange':
                for child in elem:
                    child_tag = child.tag.split('}')[-1]
                    if child_tag == 'Min' and child.text:
                        quality_range = (float(child.text), quality_range[1])
                    elif child_tag == 'Max' and child.text:
                        quality_range = (quality_range[0], float(child.text))
            
            elif tag == 'BitrateRange':
                for child in elem:
                    child_tag = child.tag.split('}')[-1]
                    if child_tag == 'Min' and child.text:
                        bitrate_range = (int(child.text), bitrate_range[1])
                    elif child_tag == 'Max' and child.text:
                        bitrate_range = (bitrate_range[0], int(child.text))
        
        # Remove duplicates and sort resolutions
        resolution_options = list(set((r.width, r.height) for r in resolution_options))
        resolution_options.sort(key=lambda r: r[0] * r[1], reverse=True)
        resolution_options = [VideoResolution(w, h) for w, h in resolution_options]
        
        return VideoEncoderOptions(
            encoding_options=list(set(encoding_options)),
            resolution_options=resolution_options,
            quality_range=quality_range,
            framerate_range=framerate_range,
            bitrate_range=bitrate_range,
            gov_length_range=gov_length_range,
            h264_profiles=list(set(h264_profiles)),
            h265_profiles=list(set(h265_profiles))
        )
    
    async def set_video_encoder_configuration(
        self,
        token: str,
        encoding: str = None,
        width: int = None,
        height: int = None,
        framerate: int = None,
        bitrate: int = None,
        quality: float = None,
        gov_length: int = None,
        profile: str = None
    ) -> bool:
        """
        Update video encoder configuration.
        Only provided parameters will be updated.
        """
        await self._ensure_media_url()
        
        # First get current configuration
        current = await self.get_video_encoder_configuration(token)
        if not current:
            print(f"Could not get current configuration for token {token}")
            return False
        
        # Use current values for unspecified parameters
        new_encoding = encoding or current.encoding
        new_width = width or current.resolution.width
        new_height = height or current.resolution.height
        new_framerate = framerate if framerate is not None else current.framerate_limit
        new_bitrate = bitrate if bitrate is not None else current.bitrate_limit
        new_quality = quality if quality is not None else current.quality
        new_gov_length = gov_length if gov_length is not None else current.gov_length
        new_profile = profile or current.profile or 'Main'
        
        # Build encoding-specific XML
        if new_encoding.upper() == 'H264':
            encoding_xml = f'''
            <tt:H264>
                <tt:GovLength>{new_gov_length}</tt:GovLength>
                <tt:H264Profile>{new_profile}</tt:H264Profile>
            </tt:H264>'''
        elif new_encoding.upper() == 'H265':
            encoding_xml = f'''
            <tt:H265>
                <tt:GovLength>{new_gov_length}</tt:GovLength>
                <tt:H265Profile>{new_profile}</tt:H265Profile>
            </tt:H265>'''
        else:
            encoding_xml = ''
        
        body = f'''
        <trt:SetVideoEncoderConfiguration>
            <trt:Configuration token="{token}">
                <tt:Name>{current.name}</tt:Name>
                <tt:UseCount>{current.use_count}</tt:UseCount>
                <tt:Encoding>{new_encoding}</tt:Encoding>
                <tt:Resolution>
                    <tt:Width>{new_width}</tt:Width>
                    <tt:Height>{new_height}</tt:Height>
                </tt:Resolution>
                <tt:Quality>{new_quality}</tt:Quality>
                <tt:RateControl>
                    <tt:FrameRateLimit>{new_framerate}</tt:FrameRateLimit>
                    <tt:EncodingInterval>1</tt:EncodingInterval>
                    <tt:BitrateLimit>{new_bitrate}</tt:BitrateLimit>
                </tt:RateControl>
                {encoding_xml}
            </trt:Configuration>
            <trt:ForcePersistence>true</trt:ForcePersistence>
        </trt:SetVideoEncoderConfiguration>
        '''
        
        response = await self._send_request(self.media_service_url, body)
        
        if response is not None:
            # Check for fault
            for elem in response.iter():
                if 'Fault' in elem.tag:
                    print(f"ONVIF SetVideoEncoderConfiguration fault")
                    return False
            print(f"Successfully updated video encoder configuration {token}")
            return True
        
        return False


async def get_camera_video_config(
    host: str, 
    port: int = 80, 
    username: str = None, 
    password: str = None
) -> Dict[str, Any]:
    """
    Get complete video configuration from a camera.
    Returns profiles, encoder configs, and available options.
    """
    print(f"get_camera_video_config: Starting for {host}:{port}")
    client = ONVIFClient(host, port, username, password)
    
    result = {
        "host": host,
        "port": port,
        "profiles": [],
        "encoder_configs": [],
        "options": None,
        "error": None
    }
    
    try:
        # Get profiles
        print("get_camera_video_config: Getting profiles...")
        profiles = await client.get_profiles()
        print(f"get_camera_video_config: Got {len(profiles)} profiles")
        result["profiles"] = [
            {
                "token": p.token,
                "name": p.name,
                "video_encoder_token": p.video_encoder_token
            }
            for p in profiles
        ]
        
        # Get encoder configurations
        print("get_camera_video_config: Getting encoder configs...")
        configs = await client.get_video_encoder_configurations()
        print(f"get_camera_video_config: Got {len(configs)} encoder configs")
        result["encoder_configs"] = [
            {
                "token": c.token,
                "name": c.name,
                "encoding": c.encoding,
                "resolution": {"width": c.resolution.width, "height": c.resolution.height},
                "quality": c.quality,
                "framerate_limit": c.framerate_limit,
                "bitrate_limit": c.bitrate_limit,
                "gov_length": c.gov_length,
                "profile": c.profile
            }
            for c in configs
        ]
        
        # Get options (from first profile if available)
        if profiles:
            print("get_camera_video_config: Getting encoder options...")
            options = await client.get_video_encoder_options(profile_token=profiles[0].token)
            if options:
                result["options"] = {
                    "encoding_options": options.encoding_options,
                    "resolution_options": [
                        {"width": r.width, "height": r.height}
                        for r in options.resolution_options
                    ],
                    "quality_range": options.quality_range,
                    "framerate_range": options.framerate_range,
                    "bitrate_range": options.bitrate_range,
                    "gov_length_range": options.gov_length_range,
                    "h264_profiles": options.h264_profiles,
                    "h265_profiles": options.h265_profiles
                }
        
        print(f"get_camera_video_config: Complete - profiles={len(result['profiles'])}, encoders={len(result['encoder_configs'])}")
    
    except Exception as e:
        print(f"get_camera_video_config: Error - {e}")
        result["error"] = str(e)
    
    return result


async def update_camera_video_config(
    host: str,
    port: int = 80,
    username: str = None,
    password: str = None,
    config_token: str = None,
    encoding: str = None,
    width: int = None,
    height: int = None,
    framerate: int = None,
    bitrate: int = None,
    quality: float = None,
    gov_length: int = None,
    profile: str = None
) -> Dict[str, Any]:
    """
    Update video encoder configuration on a camera.
    """
    client = ONVIFClient(host, port, username, password)
    
    result = {
        "success": False,
        "error": None,
        "updated_config": None
    }
    
    try:
        success = await client.set_video_encoder_configuration(
            token=config_token,
            encoding=encoding,
            width=width,
            height=height,
            framerate=framerate,
            bitrate=bitrate,
            quality=quality,
            gov_length=gov_length,
            profile=profile
        )
        
        result["success"] = success
        
        if success:
            # Get updated configuration
            updated = await client.get_video_encoder_configuration(config_token)
            if updated:
                result["updated_config"] = {
                    "token": updated.token,
                    "name": updated.name,
                    "encoding": updated.encoding,
                    "resolution": {"width": updated.resolution.width, "height": updated.resolution.height},
                    "quality": updated.quality,
                    "framerate_limit": updated.framerate_limit,
                    "bitrate_limit": updated.bitrate_limit,
                    "gov_length": updated.gov_length,
                    "profile": updated.profile
                }
        else:
            result["error"] = "Failed to update configuration"
    
    except Exception as e:
        result["error"] = str(e)
    
    return result
