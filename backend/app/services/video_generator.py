import asyncio
import logging
import httpx
from pathlib import Path

from ..config import settings
from ..models import Job, JobStatus, VideoGenerationRequest
from .job_manager import job_manager
from .replicate_client import ReplicateClient, ReplicateHTTPError, extract_first_output_url
from .settings_store import get_replicate_token, get_video_model

logger = logging.getLogger(__name__)


class ReplicateVideoService:
    """Video generation via Replicate REST API (supports start+end image, prompt, aspect ratio)."""
    
    def __init__(self):
        self.timeout_s = settings.job_timeout_seconds
        self.poll_interval_s = settings.polling_interval_seconds
    
    async def generate_video(
        self,
        request: VideoGenerationRequest,
        *,
        image_data: bytes,
        image_filename: str,
        image_content_type: str,
        motion_video_data: bytes,
        motion_video_filename: str,
        motion_video_content_type: str,
    ) -> Job:
        """Start video generation job using Replicate"""
        
        job = Job(
            job_type="video",
            status=JobStatus.PENDING,
            message="Initializing video generation...",
            metadata={
                "model": get_video_model() or settings.video_model,
                "mode": request.mode.value,
                "character_orientation": request.character_orientation.value,
                "keep_original_sound": request.keep_original_sound,
                "prompt": request.prompt,
                "provider": "replicate",
            }
        )
        await job_manager.create_job(job)
        
        # Start async processing
        asyncio.create_task(
            self._process_video_generation(
                job.id,
                request,
                image_data=image_data,
                image_filename=image_filename,
                image_content_type=image_content_type,
                motion_video_data=motion_video_data,
                motion_video_filename=motion_video_filename,
                motion_video_content_type=motion_video_content_type,
            )
        )
        
        return job
    
    async def _process_video_generation(
        self,
        job_id: str,
        request: VideoGenerationRequest,
        *,
        image_data: bytes,
        image_filename: str,
        image_content_type: str,
        motion_video_data: bytes,
        motion_video_filename: str,
        motion_video_content_type: str,
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
            model_id = get_video_model() or settings.video_model
            if not model_id:
                raise ReplicateHTTPError(
                    "Video model is not configured. Set VIDEO_MODEL on the backend (Render env vars) "
                    "or set it from the Settings dashboard."
                )

            await job_manager.update_job(job_id, progress=20, message="Uploading inputs to Replicate...")

            image_uri = await client.upload_file(
                filename=image_filename,
                content=image_data,
                content_type=image_content_type or "image/png",
            )
            video_uri = await client.upload_file(
                filename=motion_video_filename,
                content=motion_video_data,
                content_type=motion_video_content_type or "video/mp4",
            )
            
            await job_manager.update_job(
                job_id,
                progress=25,
                message="Sending to video model..."
            )
            
            await job_manager.update_job(job_id, progress=40, message="Generating video...")

            # Prompt: always include an instruction to "mount" the character image onto the driving video.
            user_prompt = (request.prompt or "").strip()
            base_prompt = (
                "Replace the character/person in the driving video with the subject from the reference image. "
                "Preserve the driving video's motion, timing, facial expressions, camera movement, framing, "
                "background, lighting, and overall style. Keep the subject's identity consistent with the "
                "reference image (face, hair, skin tone) and make the result hyper-realistic with natural "
                "blinks and stable facial features. No warping, no flicker, no text, no watermark."
            )
            final_prompt = f"{base_prompt}\n\nAdditional instructions: {user_prompt}" if user_prompt else base_prompt

            input_payload: dict = {
                "image": image_uri,
                "video": video_uri,
                "prompt": final_prompt,
                "mode": request.mode.value,
                "character_orientation": request.character_orientation.value,
                "keep_original_sound": request.keep_original_sound,
            }

            prediction = await client.create_prediction(
                model=model_id,
                input=input_payload,
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
                    
        except ReplicateHTTPError as e:
            logger.error(f"Video generation failed for job {job_id}: {e}")
            await job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                message="Video generation failed",
                error=str(e),
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
