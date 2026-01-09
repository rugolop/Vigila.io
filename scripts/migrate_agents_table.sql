-- =============================================================================
-- Vigila.io - Migración: Tabla de Agentes
-- =============================================================================
-- Este script crea la tabla de agentes para persistir la información
-- de los agentes locales en la base de datos
-- =============================================================================

-- Tabla de Agentes
CREATE TABLE IF NOT EXISTS agents (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(255) UNIQUE NOT NULL,  -- Identificador único como "agent_abc123"
    name VARCHAR(255) NOT NULL,
    
    -- Asociación con tenant
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Detalles del agente
    local_ip VARCHAR(50),
    version VARCHAR(50),
    token_hash BIGINT,  -- Hash del token de autenticación
    
    -- Estado en runtime
    cameras_count INTEGER DEFAULT 0,
    relay_status VARCHAR(50) DEFAULT 'idle',
    
    -- Tracking de estado
    is_active BOOLEAN DEFAULT TRUE,  -- Si es FALSE, el agente está marcado como eliminado
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Timestamps
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para mejor rendimiento
CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id);
CREATE INDEX IF NOT EXISTS idx_agents_tenant ON agents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name);
CREATE INDEX IF NOT EXISTS idx_agents_active ON agents(is_active);
CREATE INDEX IF NOT EXISTS idx_agents_last_seen ON agents(last_seen);

-- Índice compuesto para búsquedas de agente existente
CREATE INDEX IF NOT EXISTS idx_agents_tenant_name_ip ON agents(tenant_id, name, local_ip);

-- =============================================================================
-- VERIFICACIÓN
-- =============================================================================

-- Verificar que la tabla fue creada
SELECT 'Tabla agents creada exitosamente' AS resultado
WHERE EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'agents'
);

-- Mostrar estructura de la tabla
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'agents'
ORDER BY ordinal_position;
