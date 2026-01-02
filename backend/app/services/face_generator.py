import httpx
import asyncio
import logging
import base64
import uuid
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from ..config import settings
from ..models import Job, JobStatus, FaceGenerationRequest
from .job_manager import job_manager

logger = logging.getLogger(__name__)


class NanoBananaService:
    """Service for Nano Banana Pro face generation API"""
    
    def __init__(self):
        self.api_key = settings.nano_banana_api_key
        self.base_url = settings.nano_banana_base_url
        self.timeout = settings.job_timeout_seconds
        self.polling_interval = settings.polling_interval_seconds
    
    async def generate_face(
        self,
        request: FaceGenerationRequest,
        reference_images: List[bytes] = None
    ) -> Job:
        """Start face generation job"""
        
        # Create job
        job = Job(
            job_type="face",
            status=JobStatus.PENDING,
            message="Initializing face generation...",
            metadata={
                "prompt": request.prompt,
                "aspect_ratio": request.aspect_ratio.value,
                "mode": request.mode,
                "strength": request.strength
            }
        )
        await job_manager.create_job(job)
        
        # Start async processing
        asyncio.create_task(self._process_face_generation(job.id, request, reference_images))
        
        return job
    
    async def _process_face_generation(
        self,
        job_id: str,
        request: FaceGenerationRequest,
        reference_images: List[bytes] = None
    ):
        """Process face generation in background"""
        try:
            await job_manager.update_job(
                job_id,
                status=JobStatus.PROCESSING,
                progress=10,
                message="Preparing request..."
            )
            
            # Prepare API request
            payload = {
                "prompt": request.prompt,
                "aspect_ratio": request.aspect_ratio.value,
                "mode": request.mode,
                "strength": request.strength
            }
            
            # Add reference images if provided
            if reference_images:
                payload["images"] = [
                    base64.b64encode(img).decode("utf-8") 
                    for img in reference_images[:4]  # Max 4 images
                ]
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            await job_manager.update_job(
                job_id,
                progress=30,
                message="Sending to Nano Banana Pro..."
            )
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Submit generation request
                response = await client.post(
                    f"{self.base_url}/generate",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    raise Exception(f"API error: {response.status_code} - {response.text}")
                
                result = response.json()
                provider_job_id = result.get("job_id") or result.get("id")
                
                await job_manager.update_job(
                    job_id,
                    provider_job_id=provider_job_id,
                    progress=50,
                    message="Processing face generation..."
                )
                
                # Poll for completion
                result_url = await self._poll_for_result(client, headers, provider_job_id, job_id)
                
                if result_url:
                    # Download and save locally
                    local_url = await self._save_result(client, result_url, job_id)
                    
                    await job_manager.update_job(
                        job_id,
                        status=JobStatus.COMPLETED,
                        progress=100,
                        message="Face generation completed!",
                        result_url=local_url
                    )
                else:
                    raise Exception("No result URL received")
                    
        except Exception as e:
            logger.error(f"Face generation failed for job {job_id}: {e}")
            await job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                message="Face generation failed",
                error=str(e)
            )
    
    async def _poll_for_result(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        provider_job_id: str,
        job_id: str
    ) -> Optional[str]:
        """Poll API until job completes"""
        
        max_attempts = self.timeout // self.polling_interval
        
        for attempt in range(max_attempts):
            await asyncio.sleep(self.polling_interval)
            
            progress = min(50 + (attempt * 5), 95)
            await job_manager.update_job(
                job_id,
                progress=progress,
                message=f"Generating... ({attempt * self.polling_interval}s)"
            )
            
            try:
                response = await client.get(
                    f"{self.base_url}/jobs/{provider_job_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "").lower()
                    
                    if status in ["completed", "done", "success"]:
                        return data.get("result_url") or data.get("output", {}).get("url")
                    elif status in ["failed", "error"]:
                        raise Exception(data.get("error", "Unknown error"))
                        
            except httpx.RequestError as e:
                logger.warning(f"Polling request failed: {e}")
                continue
        
        raise Exception("Job timed out")
    
    async def _save_result(
        self,
        client: httpx.AsyncClient,
        url: str,
        job_id: str
    ) -> str:
        """Download and save result locally"""
        
        response = await client.get(url)
        response.raise_for_status()
        
        # Determine file extension
        content_type = response.headers.get("content-type", "image/png")
        ext = "png" if "png" in content_type else "jpg"
        
        filename = f"{job_id}.{ext}"
        filepath = Path(settings.storage_path) / "faces" / filename
        
        filepath.write_bytes(response.content)
        logger.info(f"Saved face result to {filepath}")
        
        return f"/storage/faces/{filename}"


# Global service instance
face_generator = NanoBananaService()

