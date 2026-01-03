from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from ..models import (
    VideoGenerationRequest, 
    VideoGenerationResponse, 
    JobStatusResponse,
    VideoMode,
    CharacterOrientation,
    JobStatus
)
from ..services.video_generator import video_generator
from ..services.job_manager import job_manager

router = APIRouter(prefix="/video", tags=["Video Generation"])


@router.post("/generate", response_model=VideoGenerationResponse)
async def generate_video(
    image: UploadFile = File(..., description="Character image (face)"),
    video: UploadFile = File(..., description="Driving/motion video"),
    mode: VideoMode = Form(VideoMode.STD),
    character_orientation: CharacterOrientation = Form(CharacterOrientation.VIDEO),
    keep_original_sound: bool = Form(False),
    prompt: str = Form("", description="Optional prompt"),
):
    """
    Generate a video from an image + driving video using Kling v2.6 Motion Control.
    
    - **image**: Start image
    - **video**: Driving video (motion reference)
    - **prompt**: Prompt
    - **mode**: std / pro
    - **character_orientation**: image / video
    - **keep_original_sound**: keep audio from the driving video
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

    # Validate driving video
    if not video.filename:
        raise HTTPException(status_code=400, detail="Driving video file required")
    video_content_type = video.content_type or ""
    if not video_content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Driving file must be a video")
    video_data = await video.read()
    if not video_data:
        raise HTTPException(status_code=400, detail="Empty video file")
    
    # Create request
    request = VideoGenerationRequest(
        prompt=prompt or "",
        mode=mode,
        character_orientation=character_orientation,
        keep_original_sound=keep_original_sound,
    )
    
    # Start generation
    job = await video_generator.generate_video(
        request,
        image_data=image_data,
        image_filename=image.filename or "image.png",
        image_content_type=content_type,
        motion_video_data=video_data,
        motion_video_filename=video.filename or "motion.mp4",
        motion_video_content_type=video_content_type,
    )
    
    return VideoGenerationResponse(
        job_id=job.id,
        status=job.status,
        message=job.message,
        created_at=job.created_at,
        provider=job.metadata.get("provider") if job.metadata else None
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
                "model": j.metadata.get("model") if j.metadata else None,
                "mode": j.metadata.get("mode") if j.metadata else None
            }
            for j in jobs[:limit]
        ]
    }

