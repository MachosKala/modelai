import httpx
import asyncio
import logging
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..config import settings
from ..models import Job, JobStatus, VideoGenerationRequest
from .job_manager import job_manager

logger = logging.getLogger(__name__)


class KlingVideoService:
    """Service for Kling 2.6 Motion Control video generation"""
    
    def __init__(self):
        self.api_key = settings.kling_api_key
        self.base_url = settings.kling_base_url
        self.timeout = settings.job_timeout_seconds
        self.polling_interval = settings.polling_interval_seconds
    
    async def generate_video(
        self,
        request: VideoGenerationRequest,
        source_image: bytes
    ) -> Job:
        """Start video generation job"""
        
        job = Job(
            job_type="video",
            status=JobStatus.PENDING,
            message="Initializing video generation...",
            metadata={
                "motion_type": request.motion_type.value,
                "duration_seconds": request.duration_seconds,
                "motion_prompt": request.motion_prompt,
                "aspect_ratio": request.aspect_ratio.value
            }
        )
        await job_manager.create_job(job)
        
        # Start async processing
        asyncio.create_task(self._process_video_generation(job.id, request, source_image))
        
        return job
    
    async def _process_video_generation(
        self,
        job_id: str,
        request: VideoGenerationRequest,
        source_image: bytes
    ):
        """Process video generation in background"""
        try:
            await job_manager.update_job(
                job_id,
                status=JobStatus.PROCESSING,
                progress=10,
                message="Preparing video request..."
            )
            
            # Motion presets for Kling 2.6
            motion_presets = {
                "natural": "Natural head movement, subtle expressions, occasional blinks",
                "dynamic": "Expressive movement, head turns, animated expressions",
                "subtle": "Minimal movement, calm breathing, soft expressions",
                "talking": "Mouth movement as if speaking, natural gestures"
            }
            
            motion_prompt = request.motion_prompt or motion_presets.get(
                request.motion_type.value, 
                motion_presets["natural"]
            )
            
            # Prepare payload for Kling API
            payload = {
                "image": base64.b64encode(source_image).decode("utf-8"),
                "prompt": motion_prompt,
                "duration": request.duration_seconds,
                "aspect_ratio": request.aspect_ratio.value,
                "motion_control": {
                    "type": request.motion_type.value,
                    "intensity": 0.7
                },
                "model": "kling-v2.6"
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            await job_manager.update_job(
                job_id,
                progress=25,
                message="Sending to Kling 2.6..."
            )
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Submit generation request
                response = await client.post(
                    f"{self.base_url}/videos/generate",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code not in [200, 201, 202]:
                    raise Exception(f"API error: {response.status_code} - {response.text}")
                
                result = response.json()
                provider_job_id = result.get("task_id") or result.get("job_id") or result.get("id")
                
                await job_manager.update_job(
                    job_id,
                    provider_job_id=provider_job_id,
                    progress=40,
                    message="Video processing started..."
                )
                
                # Poll for completion (video takes longer)
                result_url = await self._poll_for_result(client, headers, provider_job_id, job_id)
                
                if result_url:
                    local_url = await self._save_result(client, result_url, job_id)
                    
                    await job_manager.update_job(
                        job_id,
                        status=JobStatus.COMPLETED,
                        progress=100,
                        message="Video generation completed!",
                        result_url=local_url
                    )
                else:
                    raise Exception("No video URL received")
                    
        except Exception as e:
            logger.error(f"Video generation failed for job {job_id}: {e}")
            await job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                message="Video generation failed",
                error=str(e)
            )
    
    async def _poll_for_result(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        provider_job_id: str,
        job_id: str
    ) -> Optional[str]:
        """Poll API until video job completes"""
        
        # Video generation takes longer, extend timeout
        video_timeout = self.timeout * 2
        max_attempts = video_timeout // self.polling_interval
        
        for attempt in range(max_attempts):
            await asyncio.sleep(self.polling_interval)
            
            progress = min(40 + (attempt * 3), 95)
            elapsed = attempt * self.polling_interval
            await job_manager.update_job(
                job_id,
                progress=progress,
                message=f"Rendering video... ({elapsed}s)"
            )
            
            try:
                response = await client.get(
                    f"{self.base_url}/videos/{provider_job_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "").lower()
                    
                    if status in ["completed", "done", "success", "finished"]:
                        # Try multiple possible response formats
                        video_url = (
                            data.get("video_url") or 
                            data.get("result", {}).get("url") or
                            data.get("output", {}).get("video_url") or
                            data.get("works", [{}])[0].get("video", {}).get("url")
                        )
                        return video_url
                    elif status in ["failed", "error", "cancelled"]:
                        error_msg = data.get("error", {}).get("message", "Unknown error")
                        raise Exception(error_msg)
                        
            except httpx.RequestError as e:
                logger.warning(f"Video polling request failed: {e}")
                continue
        
        raise Exception("Video generation timed out")
    
    async def _save_result(
        self,
        client: httpx.AsyncClient,
        url: str,
        job_id: str
    ) -> str:
        """Download and save video locally"""
        
        response = await client.get(url)
        response.raise_for_status()
        
        filename = f"{job_id}.mp4"
        filepath = Path(settings.storage_path) / "videos" / filename
        
        filepath.write_bytes(response.content)
        logger.info(f"Saved video result to {filepath}")
        
        return f"/storage/videos/{filename}"


# Global service instance
video_generator = KlingVideoService()

