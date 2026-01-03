import asyncio
import logging
import base64
import httpx
from pathlib import Path

from ..config import settings
from ..models import Job, JobStatus, VideoGenerationRequest
from .job_manager import job_manager
from .replicate_client import ReplicateClient, extract_first_output_url
from .settings_store import get_replicate_token

logger = logging.getLogger(__name__)


class ReplicateVideoService:
    """Video generation via Replicate REST API (Kling v2.6 Motion Control)."""
    
    def __init__(self):
        self.model = settings.video_model
        self.timeout_s = settings.job_timeout_seconds
        self.poll_interval_s = settings.polling_interval_seconds
    
    async def generate_video(
        self,
        request: VideoGenerationRequest,
        source_image: bytes
    ) -> Job:
        """Start video generation job using Replicate"""
        
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
        """Process video generation in background using Replicate REST API."""
        try:
            await job_manager.update_job(
                job_id,
                status=JobStatus.PROCESSING,
                progress=10,
                message="Preparing video request..."
            )

            client = ReplicateClient(api_token=get_replicate_token())
            
            # Motion presets
            motion_presets = {
                "natural": "Natural head movement, subtle expressions, occasional blinks, slight breathing motion",
                "dynamic": "Expressive movement, head turns left and right, animated expressions, engaging gestures",
                "subtle": "Minimal movement, calm breathing, soft expressions, gentle eye movement",
                "talking": "Mouth movement as if speaking, natural gestures, expressive face, slight head nods"
            }
            
            motion_prompt = request.motion_prompt or motion_presets.get(
                request.motion_type.value, 
                motion_presets["natural"]
            )
            
            # Convert image to data URI
            img_base64 = base64.b64encode(source_image).decode("utf-8")
            image_uri = f"data:image/png;base64,{img_base64}"
            
            await job_manager.update_job(
                job_id,
                progress=25,
                message="Sending to Kling v2.6..."
            )
            
            await job_manager.update_job(job_id, progress=40, message="Generating video...")

            prediction = await client.create_prediction(
                model=self.model,
                input={
                    "image": image_uri,
                    "prompt": motion_prompt,
                    "duration": request.duration_seconds,
                    "aspect_ratio": request.aspect_ratio.value,
                },
            )
            provider_job_id = prediction.get("id")
            if not provider_job_id:
                raise Exception(f"Replicate did not return a prediction id. Response: {prediction}")
            await job_manager.update_job(job_id, provider_job_id=provider_job_id, progress=55, message="Queued...")

            def _tick(pred: dict, elapsed_s: int):
                status = (pred.get("status") or "").lower()
                progress = min(55 + int(elapsed_s / max(self.poll_interval_s, 1)) * 3, 95)
                asyncio.create_task(
                    job_manager.update_job(
                        job_id,
                        progress=progress,
                        message=f"{status}... ({elapsed_s}s)",
                    )
                )

            final_pred = await client.wait_for_prediction(
                provider_job_id,
                timeout_s=self.timeout_s,
                poll_interval_s=self.poll_interval_s,
                on_tick=_tick,
            )

            video_url = extract_first_output_url(final_pred.get("output"))
            if not video_url:
                error_msg = final_pred.get("error") or "No video URL received from Replicate"
                raise Exception(error_msg)
            
            await job_manager.update_job(
                job_id,
                progress=80,
                message="Downloading video..."
            )
            
            # Download and save locally
            local_url = await self._save_result(str(video_url), job_id)
            
            await job_manager.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=100,
                message="Video generation completed!",
                result_url=local_url
            )
                    
        except Exception as e:
            logger.error(f"Video generation failed for job {job_id}: {e}")
            await job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                message="Video generation failed",
                error=str(e)
            )
    
    async def _save_result(self, url: str, job_id: str) -> str:
        """Download and save video locally"""
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            filename = f"{job_id}.mp4"
            filepath = Path(settings.storage_path) / "videos" / filename
            
            filepath.write_bytes(response.content)
            logger.info(f"Saved video result to {filepath}")
            
            return f"/storage/videos/{filename}"


# Global service instance
video_generator = ReplicateVideoService()
