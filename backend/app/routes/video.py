from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from datetime import datetime

from ..models import (
    VideoGenerationRequest, 
    VideoGenerationResponse, 
    JobStatusResponse,
    MotionType,
    AspectRatio,
    JobStatus
)
from ..services.video_generator import video_generator
from ..services.job_manager import job_manager

router = APIRouter(prefix="/video", tags=["Video Generation"])


@router.post("/generate", response_model=VideoGenerationResponse)
async def generate_video(
    image: UploadFile = File(..., description="Source face image"),
    motion_type: MotionType = Form(MotionType.NATURAL),
    duration_seconds: int = Form(5, ge=2, le=10),
    motion_prompt: str = Form(None, description="Custom motion description"),
    aspect_ratio: AspectRatio = Form(AspectRatio.PORTRAIT)
):
    """
    Generate a video from a face image using Kling 2.6 Motion Control.
    
    - **image**: The face image to animate
    - **motion_type**: Type of motion (natural, dynamic, subtle, talking)
    - **duration_seconds**: Video duration (2-10 seconds)
    - **motion_prompt**: Optional custom motion description
    """
    
    # Validate file
    if not image.filename:
        raise HTTPException(status_code=400, detail="Image file required")
    
    content_type = image.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Read image
    image_data = await image.read()
    
    if not image_data:
        raise HTTPException(status_code=400, detail="Empty image file")
    
    # Create request
    request = VideoGenerationRequest(
        motion_type=motion_type,
        duration_seconds=duration_seconds,
        motion_prompt=motion_prompt,
        aspect_ratio=aspect_ratio
    )
    
    # Start generation
    job = await video_generator.generate_video(request, image_data)
    
    return VideoGenerationResponse(
        job_id=job.id,
        status=job.status,
        message=job.message,
        created_at=job.created_at,
        duration_seconds=duration_seconds,
        cost_credits=100
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_video_status(job_id: str):
    """Get the status of a video generation job"""
    
    job = await job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.job_type != "video":
        raise HTTPException(status_code=400, detail="Not a video generation job")
    
    return JobStatusResponse(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        message=job.message,
        created_at=job.created_at,
        completed_at=job.completed_at,
        result_url=job.result_url,
        error=job.error
    )


@router.get("/history")
async def get_video_history(limit: int = 20):
    """Get recent video generation jobs"""
    
    jobs = await job_manager.list_jobs(job_type="video")
    
    return {
        "jobs": [
            {
                "job_id": j.id,
                "status": j.status,
                "message": j.message,
                "created_at": j.created_at,
                "result_url": j.result_url,
                "duration": j.metadata.get("duration_seconds")
            }
            for j in jobs[:limit]
        ]
    }

