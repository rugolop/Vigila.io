import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres:Agc150611@localhost:5432/vigila_dev')
    
    # Check tenant_users
    users = await conn.fetch('SELECT id, tenant_id, role FROM tenant_users')
    print('Tenant Users:')
    for u in users:
        print(f"  ID: {u['id'][:30]}... | Tenant: {u['tenant_id']} | Role: {u['role']}")
    
    # Check user table  
    auth_users = await conn.fetch('SELECT id, email, role FROM "user" LIMIT 5')
    print('\nBetter Auth Users:')
    for u in auth_users:
        print(f"  ID: {u['id'][:30]}... | Email: {u['email']} | Role: {u['role']}")
    
    await conn.close()

asyncio.run(main())
