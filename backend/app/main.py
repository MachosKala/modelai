import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from .config import settings
from .routes import face, video, lipsync
from .services.job_manager import job_manager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("🚀 AI Model Generator starting up...")
    logger.info(f"📁 Storage path: {settings.storage_path}")
    logger.info(f"🔧 Debug mode: {settings.debug}")
    logger.info(f"🎤 Lip sync provider: {settings.lipsync_provider}")
    yield
    logger.info("👋 AI Model Generator shutting down...")


# Create FastAPI app
app = FastAPI(
    title="AI Model Generator",
    description="""
    🎨 **AI Model Generator MVP**
    
    Generate hyper-realistic AI models with:
    - **Face Generation**: Create new faces using Nano Banana Pro
    - **Video Generation**: Animate faces with Kling 2.6 Motion Control
    - **Lip Sync**: Add realistic voice and lip sync
    
    Each endpoint returns a `job_id` for tracking async operations.
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static storage
storage_path = Path(settings.storage_path)
storage_path.mkdir(exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(storage_path)), name="storage")

# Include routers
app.include_router(face.router, prefix="/api")
app.include_router(video.router, prefix="/api")
app.include_router(lipsync.router, prefix="/api")


# ================== Health & Status Endpoints ==================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint with API info"""
    return {
        "name": "AI Model Generator",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "face": "/api/face/generate",
            "video": "/api/video/generate",
            "lipsync": "/api/lipsync/generate"
        },
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "storage": str(storage_path.absolute()),
        "debug": settings.debug
    }


@app.get("/api/jobs/{job_id}", tags=["Jobs"])
async def get_job_status(job_id: str):
    """Get status of any job by ID"""
    
    job = await job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "result_url": job.result_url,
        "error": job.error
    }


@app.get("/api/jobs", tags=["Jobs"])
async def list_all_jobs(limit: int = 50):
    """List all recent jobs"""
    
    jobs = await job_manager.list_jobs()
    
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "progress": j.progress,
                "message": j.message,
                "created_at": j.created_at,
                "result_url": j.result_url
            }
            for j in jobs[:limit]
        ]
    }


# ================== Exception Handlers ==================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

