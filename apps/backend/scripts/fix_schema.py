import asyncio
from database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        # Check current schema search path
        result = await conn.execute(text("SHOW search_path"))
        print("Search path:", result.scalar())
        
        # List all schemas
        result2 = await conn.execute(text("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
        """))
        print("\nSchemas:", [row[0] for row in result2.fetchall()])
        
        # Check if 'user' table exists in different schemas
        result3 = await conn.execute(text("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_name IN ('user', 'tenant_users')
            ORDER BY table_schema, table_name
        """))
        print("\nTables found:")
        for row in result3.fetchall():
            print(f"  {row[0]}.{row[1]}")
        
        # Update tenant_users role to superadmin
        print("\nUpdating tenant_users role...")
        update_result = await conn.execute(
            text("""
                UPDATE tenant_users 
                SET role = 'superadmin', all_locations_access = true 
                WHERE id = '5DV1gpCWhimyQdVo3RUFp1mdnzE56T7u'
            """)
        )
        print(f"✓ Updated {update_result.rowcount} row(s)")

if __name__ == "__main__":
    asyncio.run(main())
