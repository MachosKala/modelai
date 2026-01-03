from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from datetime import datetime

from ..models import (
    LipSyncRequest, 
    LipSyncResponse, 
    JobStatusResponse,
    VoiceType,
    JobStatus
)
from ..services.lipsync_generator import lipsync_generator
from ..services.job_manager import job_manager

router = APIRouter(prefix="/lipsync", tags=["Lip Sync"])


@router.post("/generate", response_model=LipSyncResponse)
async def generate_lipsync(
    video: UploadFile = File(..., description="Source video file"),
    text: str = Form(..., description="Text to speak"),
    voice_type: VoiceType = Form(VoiceType.FEMALE_YOUNG),
    language: str = Form("en", description="Language code (en, it, es, fr, de, etc.)")
):
    """
    Add realistic voice and lip sync to a video.
    
    - **video**: The video to add lip sync to
    - **text**: The text that will be spoken
    - **voice_type**: Type of voice (female_young, female_mature, male_young, etc.)
    - **language**: Language code for proper pronunciation
    """
    
    # Validate file
    if not video.filename:
        raise HTTPException(status_code=400, detail="Video file required")
    
    content_type = video.content_type or ""
    if not (content_type.startswith("video/") or video.filename.endswith((".mp4", ".webm", ".mov"))):
        raise HTTPException(status_code=400, detail="File must be a video")
    
    # Read video
    video_data = await video.read()
    
    if not video_data:
        raise HTTPException(status_code=400, detail="Empty video file")
    
    # Validate text
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="Text too long (max 5000 characters)")
    
    # Create request
    request = LipSyncRequest(
        text=text,
        voice_type=voice_type,
        language=language
    )
    
    # Start generation
    job = await lipsync_generator.generate_lipsync(request, video_data)
    
    return LipSyncResponse(
        job_id=job.id,
        status=job.status,
        message=job.message,
        created_at=job.created_at
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_lipsync_status(job_id: str):
    """Get the status of a lip sync job"""
    
    job = await job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.job_type != "lipsync":
        raise HTTPException(status_code=400, detail="Not a lip sync job")
    
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


@router.get("/voices")
async def list_voices():
    """List available voice types"""
    
    return {
        "voices": [
            {"id": "female_young", "name": "Young Female", "description": "Youthful, energetic female voice"},
            {"id": "female_mature", "name": "Mature Female", "description": "Confident, professional female voice"},
            {"id": "female_soft", "name": "Soft Female", "description": "Gentle, soothing female voice"},
            {"id": "male_young", "name": "Young Male", "description": "Youthful, friendly male voice"},
            {"id": "male_deep", "name": "Deep Male", "description": "Deep, authoritative male voice"}
        ],
        "languages": [
            {"code": "en", "name": "English"},
            {"code": "it", "name": "Italian"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "zh", "name": "Chinese"}
        ]
    }


@router.get("/history")
async def get_lipsync_history(limit: int = 20):
    """Get recent lip sync jobs"""
    
    jobs = await job_manager.list_jobs(job_type="lipsync")
    
    return {
        "jobs": [
            {
                "job_id": j.id,
                "status": j.status,
                "message": j.message,
                "created_at": j.created_at,
                "result_url": j.result_url,
                "voice_type": j.metadata.get("voice_type"),
                "language": j.metadata.get("language")
            }
            for j in jobs[:limit]
        ]
    }

