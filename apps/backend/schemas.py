from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Literal, Dict, Any

class CameraBase(BaseModel):
    name: str
    rtsp_url: str
    is_active: bool = True
    stream_mode: Literal["auto", "direct", "ffmpeg", "agent"] = "auto"

class CameraCreate(CameraBase):
    user_id: Optional[str] = None  # Better Auth user ID (legacy)
    tenant_id: Optional[int] = None
    location_id: Optional[int] = None
    agent_id: Optional[str] = None  # Agent that manages this camera
    source_ip: Optional[str] = None  # Original IP of the camera on agent's network

class CameraUpdate(BaseModel):
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    is_active: Optional[bool] = None
    stream_mode: Optional[Literal["auto", "direct", "ffmpeg", "agent"]] = None
    tenant_id: Optional[int] = None
    location_id: Optional[int] = None

class CameraResponse(CameraBase):
    id: int
    user_id: Optional[str] = None
    tenant_id: Optional[int] = None
    location_id: Optional[int] = None
    is_recording: bool = True
    created_at: datetime

    class Config:
        from_attributes = True

class RecordingLogResponse(BaseModel):
    id: int
    camera_id: int
    start_time: datetime
    end_time: Optional[datetime]
    file_path: str

    class Config:
        from_attributes = True


# ============================================================================
# Storage Volume Schemas
# ============================================================================

StorageTypeEnum = Literal["local", "nas_smb", "nas_nfs", "usb", "s3", "azure", "gcs"]
StorageStatusEnum = Literal["active", "inactive", "error", "full"]


class StorageVolumeBase(BaseModel):
    name: str
    storage_type: StorageTypeEnum = "local"
    mount_path: Optional[str] = None
    is_primary: bool = False
    is_active: bool = True
    
    # Connection details
    host_path: Optional[str] = None  # For local/USB
    server_address: Optional[str] = None  # For NAS/Cloud
    share_name: Optional[str] = None  # SMB share or bucket name
    username: Optional[str] = None
    password: Optional[str] = None
    extra_options: Optional[str] = None  # JSON string
    
    # Settings
    retention_days: int = 7


class StorageVolumeCreate(StorageVolumeBase):
    pass


class StorageVolumeUpdate(BaseModel):
    name: Optional[str] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    retention_days: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    extra_options: Optional[str] = None


class StorageVolumeResponse(StorageVolumeBase):
    id: int
    status: StorageStatusEnum
    total_bytes: Optional[int] = None
    used_bytes: Optional[int] = None
    created_at: datetime
    last_checked: Optional[datetime] = None

    class Config:
        from_attributes = True


class StorageStats(BaseModel):
    """Storage statistics for a volume."""
    total_bytes: int
    used_bytes: int
    free_bytes: int
    usage_percent: float
    recording_count: int
    oldest_recording: Optional[datetime] = None
    newest_recording: Optional[datetime] = None


class StorageOverview(BaseModel):
    """Overview of all storage."""
    volumes: List[StorageVolumeResponse]
    total_storage_bytes: int
    total_used_bytes: int
    total_free_bytes: int
    total_recordings: int
    primary_volume_id: Optional[int] = None
