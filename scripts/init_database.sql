-- =============================================================================
-- Vigila.io - Script de Inicialización de Base de Datos
-- =============================================================================
-- Ejecutar en pgAdmin Query Tool o cualquier cliente PostgreSQL
-- Este script crea todas las tablas necesarias para la aplicación
-- =============================================================================

-- Crear la base de datos (ejecutar por separado si no existe)
-- CREATE DATABASE vigila;

-- Conectarse a la base de datos vigila antes de continuar

-- =============================================================================
-- PARTE 1: Tablas de Better Auth (Autenticación)
-- =============================================================================

-- Users table (Better Auth)
CREATE TABLE IF NOT EXISTS "user" (
    id TEXT PRIMARY KEY,
    name TEXT,
    email TEXT UNIQUE NOT NULL,
    "emailVerified" BOOLEAN DEFAULT FALSE,
    image TEXT,
    role TEXT DEFAULT 'user',
    "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sessions table
CREATE TABLE IF NOT EXISTS "session" (
    id TEXT PRIMARY KEY,
    "userId" TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    "expiresAt" TIMESTAMP WITH TIME ZONE NOT NULL,
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Accounts table (for OAuth providers)
CREATE TABLE IF NOT EXISTS "account" (
    id TEXT PRIMARY KEY,
    "userId" TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    "accountId" TEXT NOT NULL,
    "providerId" TEXT NOT NULL,
    "accessToken" TEXT,
    "refreshToken" TEXT,
    "accessTokenExpiresAt" TIMESTAMP WITH TIME ZONE,
    "refreshTokenExpiresAt" TIMESTAMP WITH TIME ZONE,
    scope TEXT,
    "idToken" TEXT,
    password TEXT,
    "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Verification tokens table
CREATE TABLE IF NOT EXISTS "verification" (
    id TEXT PRIMARY KEY,
    identifier TEXT NOT NULL,
    value TEXT NOT NULL,
    "expiresAt" TIMESTAMP WITH TIME ZONE NOT NULL,
    "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- PARTE 2: Tablas Multi-Tenant (Vigila.io Backend)
-- =============================================================================

-- Tenants (Organizaciones/Clientes)
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

-- Tenant Users (Usuarios vinculados a un tenant)
CREATE TABLE IF NOT EXISTS tenant_users (
    id VARCHAR(255) PRIMARY KEY,  -- Same as Better Auth user ID
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'viewer',
    all_locations_access BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Locations (Ubicaciones físicas)
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(500),
    city VARCHAR(100),
    country VARCHAR(100),
    latitude VARCHAR(50),
    longitude VARCHAR(50),
    timezone VARCHAR(50) DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User-Locations (Many-to-Many)
CREATE TABLE IF NOT EXISTS user_locations (
    user_id VARCHAR(255) REFERENCES tenant_users(id) ON DELETE CASCADE,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, location_id)
);

-- Cameras
CREATE TABLE IF NOT EXISTS cameras (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    rtsp_url VARCHAR(500) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_recording BOOLEAN DEFAULT TRUE,
    stream_mode VARCHAR(50) DEFAULT 'auto',
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    user_id VARCHAR(255),  -- Legacy field
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Storage Volumes
CREATE TABLE IF NOT EXISTS storage_volumes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    storage_type VARCHAR(50) DEFAULT 'local',
    mount_path VARCHAR(500) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    status VARCHAR(50) DEFAULT 'inactive',
    host_path VARCHAR(500),
    server_address VARCHAR(255),
    share_name VARCHAR(255),
    username VARCHAR(255),
    password VARCHAR(255),
    extra_options TEXT,
    total_bytes BIGINT,
    used_bytes BIGINT,
    retention_days INTEGER DEFAULT 7,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_checked TIMESTAMP WITH TIME ZONE
);

-- Users (Legacy - tabla simple de usuarios)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Recording Logs
CREATE TABLE IF NOT EXISTS recording_logs (
    id SERIAL PRIMARY KEY,
    camera_id INTEGER REFERENCES cameras(id) ON DELETE CASCADE,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    file_path VARCHAR(500) NOT NULL
);

-- =============================================================================
-- PARTE 3: Índices para mejor rendimiento
-- =============================================================================

-- Better Auth indexes
CREATE INDEX IF NOT EXISTS idx_session_user_id ON "session"("userId");
CREATE INDEX IF NOT EXISTS idx_session_token ON "session"(token);
CREATE INDEX IF NOT EXISTS idx_account_user_id ON "account"("userId");
CREATE INDEX IF NOT EXISTS idx_account_provider ON "account"("providerId", "accountId");
CREATE INDEX IF NOT EXISTS idx_user_email ON "user"(email);

-- Multi-tenant indexes
CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant ON tenant_users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_locations_tenant ON locations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cameras_tenant ON cameras(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cameras_location ON cameras(location_id);
CREATE INDEX IF NOT EXISTS idx_cameras_rtsp ON cameras(rtsp_url);
CREATE INDEX IF NOT EXISTS idx_recording_logs_camera ON recording_logs(camera_id);
CREATE INDEX IF NOT EXISTS idx_recording_logs_start ON recording_logs(start_time);

-- =============================================================================
-- PARTE 4: Datos iniciales (Opcional)
-- =============================================================================

-- Crear tenant por defecto
INSERT INTO tenants (name, slug, status, max_cameras, max_users, max_locations, storage_quota_gb)
VALUES ('Default Tenant', 'default', 'active', 50, 10, 10, 500)
ON CONFLICT (slug) DO NOTHING;

-- Crear volumen de almacenamiento por defecto
INSERT INTO storage_volumes (name, storage_type, mount_path, is_primary, is_active, status, retention_days)
VALUES ('Local Storage', 'local', '/recordings', TRUE, TRUE, 'active', 30)
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- VERIFICACIÓN
-- =============================================================================

-- Listar todas las tablas creadas
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

