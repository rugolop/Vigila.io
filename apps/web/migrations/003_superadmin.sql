-- ============================================================================
-- Migration 003: Add superadmin role and assign to rugolop@gmail.com
-- ============================================================================

-- Note: The role enum doesn't need alteration since PostgreSQL stores it as varchar
-- The UserRole enum in Python will handle the new 'superadmin' value

-- First, get the user ID for rugolop@gmail.com from Better Auth's user table
DO $$
DECLARE
    v_user_id TEXT;
    v_default_tenant_id INTEGER;
BEGIN
    -- Get user ID from Better Auth user table
    SELECT id INTO v_user_id 
    FROM "user" 
    WHERE email = 'rugolop@gmail.com'
    LIMIT 1;
    
    IF v_user_id IS NULL THEN
        RAISE NOTICE 'User rugolop@gmail.com not found in user table';
        RETURN;
    END IF;
    
    RAISE NOTICE 'Found user ID: %', v_user_id;
    
    -- Get or create default tenant
    SELECT id INTO v_default_tenant_id 
    FROM tenants 
    WHERE slug = 'default'
    LIMIT 1;
    
    IF v_default_tenant_id IS NULL THEN
        INSERT INTO tenants (name, slug, status, max_cameras, max_users, max_locations, storage_quota_gb)
        VALUES ('Organización por Defecto', 'default', 'active', 1000, 1000, 500, 10000)
        RETURNING id INTO v_default_tenant_id;
        RAISE NOTICE 'Created default tenant with ID: %', v_default_tenant_id;
    END IF;
    
    -- Check if user already exists in tenant_users
    IF EXISTS (SELECT 1 FROM tenant_users WHERE id = v_user_id) THEN
        -- Update existing user to superadmin
        UPDATE tenant_users 
        SET role = 'superadmin', 
            all_locations_access = true,
            updated_at = NOW()
        WHERE id = v_user_id;
        RAISE NOTICE 'Updated user % to superadmin', v_user_id;
    ELSE
        -- Insert new tenant_user as superadmin
        INSERT INTO tenant_users (id, tenant_id, role, all_locations_access, is_active, created_at, updated_at)
        VALUES (v_user_id, v_default_tenant_id, 'superadmin', true, true, NOW(), NOW());
        RAISE NOTICE 'Created superadmin user %', v_user_id;
    END IF;
END $$;

-- Verify the result
SELECT 
    tu.id,
    tu.role,
    tu.all_locations_access,
    u.email,
    t.name as tenant_name
FROM tenant_users tu
JOIN "user" u ON tu.id = u.id
JOIN tenants t ON tu.tenant_id = t.id
WHERE u.email = 'rugolop@gmail.com';
