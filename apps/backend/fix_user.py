import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres:Agc150611@localhost:5432/vigila_dev')
    
    user_id = '5DV1gpCWhimyQdVo3RUFp1mdnzE56T7u'
    
    # Check if tenant exists
    tenant = await conn.fetchrow("SELECT id, name FROM tenants WHERE slug = 'default'")
    
    if not tenant:
        print("Creating default tenant...")
        tenant_id = await conn.fetchval("""
            INSERT INTO tenants (name, slug, max_cameras, max_users, max_locations, storage_quota_gb)
            VALUES ('Organización por Defecto', 'default', 100, 100, 50, 1000)
            RETURNING id
        """)
        print(f"✓ Created tenant ID: {tenant_id}")
    else:
        tenant_id = tenant['id']
        print(f"✓ Using existing tenant: {tenant['name']} (ID: {tenant_id})")
    
    # Check if user is already in tenant_users
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM tenant_users WHERE id = $1)",
        user_id
    )
    
    if exists:
        print(f"✓ User already in tenant_users")
    else:
        print(f"Creating tenant_user entry...")
        await conn.execute("""
            INSERT INTO tenant_users (id, tenant_id, role, all_locations_access, is_active)
            VALUES ($1, $2, 'admin', true, true)
        """, user_id, tenant_id)
        print(f"✓ Created tenant_user entry")
    
    # Verify
    result = await conn.fetchrow("""
        SELECT tu.id, tu.tenant_id, tu.role, t.name as tenant_name
        FROM tenant_users tu
        JOIN tenants t ON tu.tenant_id = t.id
        WHERE tu.id = $1
    """, user_id)
    
    if result:
        print(f"\n✓ User configuration:")
        print(f"  ID: {result['id']}")
        print(f"  Tenant: {result['tenant_name']} (ID: {result['tenant_id']})")
        print(f"  Role: {result['role']}")
    
    await conn.close()

asyncio.run(main())
