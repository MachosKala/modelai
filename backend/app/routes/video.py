from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from ..models import (
    VideoGenerationRequest, 
    VideoGenerationResponse, 
    JobStatusResponse,
    VideoAspectRatio,
    JobStatus
)
from ..services.video_generator import video_generator
from ..services.job_manager import job_manager

router = APIRouter(prefix="/video", tags=["Video Generation"])


@router.post("/generate", response_model=VideoGenerationResponse)
async def generate_video(
    image: UploadFile = File(..., description="Start image"),
    end_image: UploadFile | None = File(default=None, description="Optional end image"),
    mode: str = Form("", description="Optional mode (model-specific)"),
    prompt: str = Form("", description="Optional prompt"),
    aspect_ratio: VideoAspectRatio = Form(VideoAspectRatio.LANDSCAPE)
):
    """
    Generate a video from an image using the configured Replicate video model.
    
    - **image**: Start image
    - **end_image**: Optional end image
    - **prompt**: Prompt
    - **aspect_ratio**: 16:9 or 9:16
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

    end_image_data: bytes | None = None
    if end_image and end_image.filename:
        end_content_type = end_image.content_type or ""
        if not end_content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="End image must be an image")
        end_image_data = await end_image.read()
        if not end_image_data:
            end_image_data = None
    
    # Create request
    request = VideoGenerationRequest(
        mode=mode.strip() or None,
        prompt=prompt or "",
        aspect_ratio=aspect_ratio
    )
    
    # Start generation
    job = await video_generator.generate_video(request, image_data, end_image_data=end_image_data)
    
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
                "aspect_ratio": j.metadata.get("aspect_ratio") if j.metadata else None
            }
            for j in jobs[:limit]
        ]
    }

