from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import engine, Base, AsyncSessionLocal
from routers import cameras, recordings, storage, tenants, locations, users, agents, user_management
from services.storage_manager import start_storage_manager, stop_storage_manager
from services.mediamtx import restore_camera_path, sanitize_path_name
from sqlalchemy.future import select
from models import Camera, Tenant, Location
import asyncio


async def restore_all_cameras():
    """Restore all active camera paths to MediaMTX on startup."""
    print("Restoring camera streams to MediaMTX...")
    
    async with AsyncSessionLocal() as db:
        # Get all active cameras with their tenant and location info
        result = await db.execute(
            select(Camera, Tenant, Location)
            .outerjoin(Tenant, Camera.tenant_id == Tenant.id)
            .outerjoin(Location, Camera.location_id == Location.id)
            .where(Camera.is_active == True)
        )
        cameras_data = result.all()
        
        restored = 0
        failed = 0
        
        for camera, tenant, location in cameras_data:
            tenant_slug = tenant.slug if tenant else None
            location_name = location.name if location else None
            
            success = await restore_camera_path(
                camera_name=camera.name,
                rtsp_url=camera.rtsp_url,
                stream_mode=camera.stream_mode or "auto",
                tenant_slug=tenant_slug,
                location_name=location_name,
                is_recording=camera.is_recording
            )
            
            if success:
                restored += 1
            else:
                failed += 1
            
            # Small delay between cameras to avoid overwhelming MediaMTX
            await asyncio.sleep(1)
        
        print(f"Camera restoration complete: {restored} restored, {failed} failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize default storage volume
    async with AsyncSessionLocal() as db:
        await storage.initialize_default_storage(db)
    
    # Restore camera streams to MediaMTX
    await restore_all_cameras()
    
    # Start storage cleanup manager
    await start_storage_manager()
    
    yield
    
    # Stop storage cleanup manager on shutdown
    await stop_storage_manager()

from fastapi.staticfiles import StaticFiles
import os

# Disable automatic redirect_slashes to avoid 307 redirects that break HTTPS->HTTP
app = FastAPI(title="Smart DVR API", lifespan=lifespan, redirect_slashes=False)

# Configure CORS
cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:3000")
cors_origins = [origin.strip() for origin in cors_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
app.include_router(user_management.router)
app.include_router(agents.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Smart DVR Backend is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}
