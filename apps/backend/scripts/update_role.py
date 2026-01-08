import asyncio
from database import engine
from sqlalchemy import text

async def main():
    user_id = "5DV1gpCWhimyQdVo3RUFp1mdnzE56T7u"
    
    async with engine.begin() as conn:
        # Update the role to admin
        result = await conn.execute(
            text('''
                UPDATE tenant_users 
                SET role = 'admin', 
                    all_locations_access = true 
                WHERE id = :user_id
            '''),
            {"user_id": user_id}
        )
        
        print(f"✓ Updated {result.rowcount} user(s)")
        
        # Verify the update
        check_result = await conn.execute(
            text('SELECT id, role, all_locations_access FROM tenant_users WHERE id = :user_id'),
            {"user_id": user_id}
        )
        row = check_result.fetchone()
        if row:
            print(f"✓ Verified - Role: {row[1]}, All Locations Access: {row[2]}")
        else:
            print("✗ User not found after update")

if __name__ == "__main__":
    asyncio.run(main())
