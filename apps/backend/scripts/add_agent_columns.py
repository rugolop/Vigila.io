"""
Script to add missing columns to agents table.
Run this if you get "no existe la columna agents.cameras_count" error.
"""
import asyncio
from sqlalchemy import text
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine

async def add_columns():
    async with engine.begin() as conn:
        print("Adding cameras_count column...")
        await conn.execute(text(
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS cameras_count INTEGER DEFAULT 0"
        ))
        
        print("Adding relay_status column...")
        await conn.execute(text(
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS relay_status VARCHAR(50) DEFAULT 'idle'"
        ))
        
        print("Columns added successfully!")

if __name__ == "__main__":
    asyncio.run(add_columns())
