import asyncio
import logging
import base64
import httpx
from pathlib import Path
from typing import List

from ..config import settings
from ..models import Job, JobStatus, FaceGenerationRequest
from .job_manager import job_manager
from .replicate_client import ReplicateClient, ReplicateHTTPError, extract_first_output_url
from .settings_store import get_face_model, get_replicate_token

logger = logging.getLogger(__name__)


class ReplicateFaceService:
    """Face generation via Replicate REST API (Nano Banana Pro)."""
    
    def __init__(self):
        self.timeout_s = settings.job_timeout_seconds
        self.poll_interval_s = settings.polling_interval_seconds
    
    async def generate_face(
        self,
        request: FaceGenerationRequest,
        reference_images: List[bytes] = None
    ) -> Job:
        """Start face generation job using Replicate"""
        
        # Create job
        job = Job(
            job_type="face",
            status=JobStatus.PENDING,
            message="Initializing face generation...",
            metadata={
                "prompt": request.prompt,
                "aspect_ratio": request.aspect_ratio.value
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
        """Process face generation in background using Replicate REST API."""
        try:
            await job_manager.update_job(
                job_id,
                status=JobStatus.PROCESSING,
                progress=10,
                message="Preparing request..."
            )
            
            client = ReplicateClient(api_token=get_replicate_token())
            model_id = get_face_model() or settings.face_model
            if not model_id:
                raise ReplicateHTTPError(
                    "Face model is not configured. Set FACE_MODEL on the backend (Render env vars) "
                    "or set it from the Settings dashboard."
                )
            
            await job_manager.update_job(
                job_id,
                progress=30,
                message="Sending to Nano Banana Pro..."
            )
            
            # Prepare minimal input payload (model schemas differ; keep it lean)
            input_params = {
                "prompt": request.prompt,
            }
            
            # Add reference image if provided (for img2img)
            if reference_images and len(reference_images) > 0:
                # Convert first image to data URI
                img_base64 = base64.b64encode(reference_images[0]).decode("utf-8")
                input_params["image"] = f"data:image/png;base64,{img_base64}"
            if request.aspect_ratio.value != "auto":
                input_params["aspect_ratio"] = request.aspect_ratio.value
            
            await job_manager.update_job(
                job_id,
                progress=50,
                message="Generating face with AI..."
            )
            
            # Start prediction
            prediction = await client.create_prediction(model=model_id, input=input_params)
            provider_job_id = prediction.get("id")
            if not provider_job_id:
                raise Exception(f"Replicate did not return a prediction id. Response: {prediction}")
            await job_manager.update_job(job_id, provider_job_id=provider_job_id, progress=60, message="Queued...")

            # Poll to completion
            def _tick(pred: dict, elapsed_s: int):
                status = (pred.get("status") or "").lower()
                progress = min(60 + int(elapsed_s / max(self.poll_interval_s, 1)) * 3, 95)
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
            
            await job_manager.update_job(
                job_id,
                progress=80,
                message="Downloading result..."
            )

            output = final_pred.get("output")
            result_url = extract_first_output_url(output)
            
            if result_url:
                # Download and save locally
                local_url = await self._save_result(str(result_url), job_id)
                
                await job_manager.update_job(
                    job_id,
                    status=JobStatus.COMPLETED,
                    progress=100,
                    message="Face generation completed!",
                    result_url=local_url
                )
            else:
                error_msg = final_pred.get("error") or "No output URL received from Replicate"
                raise Exception(error_msg)
                    
        except ReplicateHTTPError as e:
            logger.error(f"Face generation failed for job {job_id}: {e}")
            await job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                message="Face generation failed",
                error=str(e),
            )
        except Exception as e:
            logger.error(f"Face generation failed for job {job_id}: {e}")
            await job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                message="Face generation failed",
                error=str(e)
            )
    
    async def _save_result(self, url: str, job_id: str) -> str:
        """Download and save result locally"""
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Determine file extension
            content_type = response.headers.get("content-type", "image/png")
            ext = "png" if "png" in content_type else "jpg" if "jpeg" in content_type or "jpg" in content_type else "webp"
            
            filename = f"{job_id}.{ext}"
            filepath = Path(settings.storage_path) / "faces" / filename
            
            filepath.write_bytes(response.content)
            logger.info(f"Saved face result to {filepath}")
            
            return f"/storage/faces/{filename}"


# Global service instance
face_generator = ReplicateFaceService()
