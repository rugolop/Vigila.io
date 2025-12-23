-- =============================================================================
-- Multi-Tenant System Migration
-- Vigila.io - Version 2.0
-- =============================================================================

-- Tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    max_cameras INTEGER DEFAULT 10,
    max_users INTEGER DEFAULT 5,
    max_locations INTEGER DEFAULT 3,
    storage_quota_gb INTEGER DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tenant Users table (links Better Auth users to tenants with roles)
CREATE TABLE IF NOT EXISTS tenant_users (
    id VARCHAR(255) PRIMARY KEY,  -- Same as Better Auth user ID
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'viewer',
    all_locations_access BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Locations table
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    city VARCHAR(100),
    country VARCHAR(100),
    latitude VARCHAR(50),
    longitude VARCHAR(50),
    timezone VARCHAR(50) DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User-Locations association table (many-to-many)
CREATE TABLE IF NOT EXISTS user_locations (
    user_id VARCHAR(255) REFERENCES tenant_users(id) ON DELETE CASCADE,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, location_id)
);

-- Add tenant_id and location_id to cameras table
ALTER TABLE cameras 
    ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Remove unique constraint on rtsp_url if exists (for multi-tenant)
ALTER TABLE cameras DROP CONSTRAINT IF EXISTS cameras_rtsp_url_key;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant ON tenant_users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_role ON tenant_users(role);
CREATE INDEX IF NOT EXISTS idx_locations_tenant ON locations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cameras_tenant ON cameras(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cameras_location ON cameras(location_id);
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);

-- =============================================================================
-- Update Better Auth user table to include role (for quick access)
-- =============================================================================
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'viewer';

-- =============================================================================
-- Create default tenant for existing data
-- =============================================================================
INSERT INTO tenants (name, slug, status, max_cameras, max_users, max_locations)
VALUES ('Default Organization', 'default', 'active', 100, 50, 20)
ON CONFLICT (slug) DO NOTHING;

-- =============================================================================
-- Comments for documentation
-- =============================================================================
COMMENT ON TABLE tenants IS 'Organizations/clients using the system';
COMMENT ON TABLE tenant_users IS 'Links Better Auth users to tenants with specific roles';
COMMENT ON TABLE locations IS 'Physical locations/sites with cameras';
COMMENT ON TABLE user_locations IS 'Many-to-many relationship between users and locations';
COMMENT ON COLUMN tenant_users.role IS 'admin: full access, operator: live + recordings, viewer: live only';
COMMENT ON COLUMN tenant_users.all_locations_access IS 'If true, user can access all locations in tenant';
