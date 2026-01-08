"""
Script to check and create Better Auth tables in PostgreSQL.
Run this to verify the database setup.
"""
import asyncio
import asyncpg

DATABASE_URL = "postgresql://postgres:Agc150611@localhost:5432/vigila_dev"

async def check_tables():
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Check if 'user' table exists
        result = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        print("Tables in database vigila_dev:")
        print("=" * 50)
        for row in result:
            print(f"  - {row['table_name']}")
        
        # Check specifically for Better Auth tables
        better_auth_tables = ['user', 'session', 'account', 'verification']
        print("\nBetter Auth tables status:")
        print("=" * 50)
        for table in better_auth_tables:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
                table
            )
            status = "✓ EXISTS" if exists else "✗ MISSING"
            print(f"  {table}: {status}")
        
        # Check tenant_users table
        tenant_users_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tenant_users')"
        )
        print(f"\nBackend tables status:")
        print("=" * 50)
        print(f"  tenant_users: {'✓ EXISTS' if tenant_users_exists else '✗ MISSING'}")
        
        # If tenant_users exists, show some data
        if tenant_users_exists:
            users = await conn.fetch("SELECT id, tenant_id, role FROM tenant_users LIMIT 5")
            if users:
                print("\nSample tenant_users data:")
                print("=" * 50)
                for user in users:
                    print(f"  ID: {user['id'][:20]}... | Tenant: {user['tenant_id']} | Role: {user['role']}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_tables())
