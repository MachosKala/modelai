from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional
from datetime import datetime

from ..models import (
    FaceGenerationRequest, 
    FaceGenerationResponse, 
    JobStatusResponse,
    AspectRatio,
    JobStatus
)
from ..services.face_generator import face_generator
from ..services.job_manager import job_manager

router = APIRouter(prefix="/face", tags=["Face Generation"])


@router.post("/generate", response_model=FaceGenerationResponse)
async def generate_face(
    prompt: str = Form(..., description="Description of the face to generate"),
    aspect_ratio: AspectRatio = Form(AspectRatio.AUTO),
    images: List[UploadFile] = File(default=[], description="Optional reference images (max 4)")
):
    """
    Generate a new AI face using Nano Banana Pro.
    
    - **prompt**: Describe the face characteristics (e.g., "young woman with green eyes, freckles")
    - **images**: Optional reference images to guide the generation
    """
    
    # Read reference images
    reference_images = []
    for img in images[:4]:  # Max 4 images
        if img.filename:
            content = await img.read()
            if content:
                reference_images.append(content)
    
    # Create request
    request = FaceGenerationRequest(
        prompt=prompt,
        aspect_ratio=aspect_ratio
    )
    
    # Start generation
    job = await face_generator.generate_face(request, reference_images or None)
    
    return FaceGenerationResponse(
        job_id=job.id,
        status=job.status,
        message=job.message,
        created_at=job.created_at
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_face_status(job_id: str):
    """Get the status of a face generation job"""
    
    job = await job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.job_type != "face":
        raise HTTPException(status_code=400, detail="Not a face generation job")
    
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
async def get_face_history(limit: int = 20):
    """Get recent face generation jobs"""
    
    jobs = await job_manager.list_jobs(job_type="face")
    
    return {
        "jobs": [
            {
                "job_id": j.id,
                "status": j.status,
                "message": j.message,
                "created_at": j.created_at,
                "result_url": j.result_url
            }
            for j in jobs[:limit]
        ]
    }

