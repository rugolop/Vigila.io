from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import engine, Base, AsyncSessionLocal
from routers import cameras, recordings, storage, tenants, locations, users

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize default storage volume
    async with AsyncSessionLocal() as db:
        await storage.initialize_default_storage(db)
    
    yield

from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="Smart DVR API", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure recordings directory exists
os.makedirs("/recordings", exist_ok=True)

app.mount("/media", StaticFiles(directory="/recordings"), name="media")

# Include routers
app.include_router(cameras.router)
app.include_router(recordings.router)
app.include_router(storage.router)
app.include_router(tenants.router)
app.include_router(locations.router)
app.include_router(users.router)

@app.get("/")
async def root():
    return {"message": "Smart DVR Backend is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}
