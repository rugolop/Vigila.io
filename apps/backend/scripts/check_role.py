import asyncio
from database import engine
from sqlalchemy import text

async def main():
    user_id = "5DV1gpCWhimyQdVo3RUFp1mdnzE56T7u"
    
    async with engine.connect() as conn:
        # Check tenant_users table
        result = await conn.execute(
            text('SELECT id, tenant_id, role, all_locations_access, is_active FROM tenant_users WHERE id = :user_id'),
            {"user_id": user_id}
        )
        tenant_user_row = result.fetchone()
        print("Tenant user:")
        if tenant_user_row:
            print(f"  ID: {tenant_user_row[0]}")
            print(f"  Tenant ID: {tenant_user_row[1]}")
            print(f"  Role: {tenant_user_row[2]}")
            print(f"  All Locations Access: {tenant_user_row[3]}")
            print(f"  Is Active: {tenant_user_row[4]}")
        else:
            print("  Not found")

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
