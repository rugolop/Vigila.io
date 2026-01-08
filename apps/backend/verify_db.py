import asyncpg
import asyncio
import sys

async def main():
    user_id = "5DV1gpCWhimyQdVo3RUFp1mdnzE56T7u"
    
    # Connect directly to PostgreSQL
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password='Agc150611',
        database='vigila_dev'
    )
    
    try:
        # Check Better Auth user table
        sys.stdout.write("=== Better Auth 'user' table ===\n")
        sys.stdout.flush()
        result = await conn.fetch(
            'SELECT id, email, role FROM "user" WHERE id = $1',
            user_id
        )
        if result:
            for row in result:
                sys.stdout.write(f"  ID: {row['id']}\n")
                sys.stdout.write(f"  Email: {row['email']}\n")
                sys.stdout.write(f"  Role: {row['role']}\n")
                sys.stdout.flush()
        else:
            sys.stdout.write("  Not found\n")
            sys.stdout.flush()
        
        sys.stdout.write("\n")
        sys.stdout.flush()
        
        # Check tenant_users table
        sys.stdout.write("=== Backend 'tenant_users' table ===\n")
        sys.stdout.flush()
        result2 = await conn.fetch(
            'SELECT id, tenant_id, role, all_locations_access, is_active FROM tenant_users WHERE id = $1',
            user_id
        )
        if result2:
            for row in result2:
                sys.stdout.write(f"  ID: {row['id']}\n")
                sys.stdout.write(f"  Tenant ID: {row['tenant_id']}\n")
                sys.stdout.write(f"  Role: {row['role']}\n")
                sys.stdout.write(f"  All Locations Access: {row['all_locations_access']}\n")
                sys.stdout.write(f"  Is Active: {row['is_active']}\n")
                sys.stdout.flush()
        else:
            sys.stdout.write("  Not found\n")
            sys.stdout.flush()
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
