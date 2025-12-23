from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, BigInteger, Text, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


# =============================================================================
# Enums
# =============================================================================

class StreamMode(str, enum.Enum):
    """Stream connection mode for cameras."""
    AUTO = "auto"           # Auto-detect (try direct first, fallback to ffmpeg)
    DIRECT = "direct"       # Direct RTSP connection
    FFMPEG = "ffmpeg"       # FFmpeg proxy (for cameras with back channel issues)


class StorageType(str, enum.Enum):
    """Type of storage volume."""
    LOCAL = "local"         # Local directory
    NAS_SMB = "nas_smb"     # NAS via SMB/CIFS
    NAS_NFS = "nas_nfs"     # NAS via NFS
    USB = "usb"             # USB external drive
    S3 = "s3"               # Amazon S3 / compatible (MinIO, etc.)
    AZURE = "azure"         # Azure Blob Storage
    GCS = "gcs"             # Google Cloud Storage


class StorageStatus(str, enum.Enum):
    """Status of storage volume."""
    ACTIVE = "active"       # Mounted and in use
    INACTIVE = "inactive"   # Configured but not mounted
    ERROR = "error"         # Mount/connection failed
    FULL = "full"           # No space left


class UserRole(str, enum.Enum):
    """User roles with different permissions."""
    SUPERADMIN = "superadmin"  # Full access across ALL tenants
    ADMIN = "admin"            # Full access within their tenant
    OPERATOR = "operator"      # Access to LiveStream and view recordings
    VIEWER = "viewer"          # Only live view access


class TenantStatus(str, enum.Enum):
    """Tenant account status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"


# =============================================================================
# Association Tables (Many-to-Many)
# =============================================================================

# Users can access multiple locations
user_locations = Table(
    'user_locations',
    Base.metadata,
    Column('user_id', String, ForeignKey('tenant_users.id'), primary_key=True),
    Column('location_id', Integer, ForeignKey('locations.id'), primary_key=True)
)


# =============================================================================
# Multi-Tenant Models
# =============================================================================

class Tenant(Base):
    """
    Tenant/Client organization.
    Each tenant has their own users, locations, and cameras.
    """
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String, unique=True, index=True)  # URL-friendly identifier
    status = Column(String, default=TenantStatus.ACTIVE.value)
    
    # Contact info
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    
    # Subscription/limits
    max_cameras = Column(Integer, default=10)
    max_users = Column(Integer, default=5)
    max_locations = Column(Integer, default=3)
    storage_quota_gb = Column(Integer, default=100)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    users = relationship("TenantUser", back_populates="tenant", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="tenant", cascade="all, delete-orphan")
    cameras = relationship("Camera", back_populates="tenant", cascade="all, delete-orphan")


class TenantUser(Base):
    """
    User within a tenant with specific role.
    Links Better Auth user to a tenant.
    """
    __tablename__ = "tenant_users"

    id = Column(String, primary_key=True)  # Same as Better Auth user ID
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    role = Column(String, default=UserRole.VIEWER.value)
    
    # User can be assigned to specific locations or all (null = all)
    all_locations_access = Column(Boolean, default=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    locations = relationship("Location", secondary=user_locations, back_populates="users")


class Location(Base):
    """
    Physical location/site with cameras.
    Examples: Office Building, Warehouse, Store Branch
    """
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, index=True)
    
    # Address
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)
    
    # Geolocation (optional)
    latitude = Column(String, nullable=True)
    longitude = Column(String, nullable=True)
    
    # Settings
    timezone = Column(String, default="UTC")
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="locations")
    cameras = relationship("Camera", back_populates="location", cascade="all, delete-orphan")
    users = relationship("TenantUser", secondary=user_locations, back_populates="locations")


# =============================================================================
# Updated Camera Model
# =============================================================================

class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    rtsp_url = Column(String, index=True)  # Removed unique constraint for multi-tenant
    is_active = Column(Boolean, default=True)
    stream_mode = Column(String, default=StreamMode.AUTO.value)
    
    # Multi-tenant relations
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    
    # Legacy field (kept for backwards compatibility, will be removed later)
    user_id = Column(String, index=True, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="cameras")
    location = relationship("Location", back_populates="cameras")
    recordings = relationship("RecordingLog", back_populates="camera")


class StorageVolume(Base):
    """Storage volume configuration for recordings."""
    __tablename__ = "storage_volumes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)  # User-friendly name
    storage_type = Column(String, default=StorageType.LOCAL.value)
    
    # Mount configuration
    mount_path = Column(String)  # Path where volume is mounted inside container
    is_primary = Column(Boolean, default=False)  # Primary volume for new recordings
    is_active = Column(Boolean, default=True)
    status = Column(String, default=StorageStatus.INACTIVE.value)
    
    # Connection details (varies by type)
    # For LOCAL: host_path (path on host machine)
    # For NAS_SMB: //server/share, username, password
    # For NAS_NFS: server:/export/path
    # For USB: /dev/sdX or UUID
    # For S3: bucket name, region, access_key, secret_key
    # For Azure: container, connection_string
    host_path = Column(String, nullable=True)  # For local/USB
    server_address = Column(String, nullable=True)  # For NAS/Cloud
    share_name = Column(String, nullable=True)  # SMB share or bucket name
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)  # Encrypted in production
    extra_options = Column(Text, nullable=True)  # JSON for additional options
    
    # Storage metrics
    total_bytes = Column(BigInteger, nullable=True)
    used_bytes = Column(BigInteger, nullable=True)
    retention_days = Column(Integer, default=7)  # Auto-delete after X days
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_checked = Column(DateTime(timezone=True), nullable=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RecordingLog(Base):
    __tablename__ = "recording_logs"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"))
    start_time = Column(DateTime(timezone=True), index=True)
    end_time = Column(DateTime(timezone=True))
    file_path = Column(String)
    
    camera = relationship("Camera", back_populates="recordings")
