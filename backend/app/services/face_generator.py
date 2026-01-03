import replicate
import asyncio
import logging
import base64
import httpx
import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from ..config import settings
from ..models import Job, JobStatus, FaceGenerationRequest
from .job_manager import job_manager

logger = logging.getLogger(__name__)


class ReplicateFaceService:
    """Service for face generation using Replicate API with Nano Banana Pro"""
    
    def __init__(self):
        self.api_token = settings.replicate_api_token
        # Available face generation models on Replicate
        self.models = {
            "nano-banana": "nanobanana/nano-banana-pro",
            "realistic": "lucataco/sdxl-lightning-4step:fast",
            "artistic": "stability-ai/sdxl:latest"
        }
        self.timeout = settings.job_timeout_seconds
    
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
        """Process face generation in background using Replicate"""
        try:
            await job_manager.update_job(
                job_id,
                status=JobStatus.PROCESSING,
                progress=10,
                message="Preparing request for Replicate..."
            )
            
            # Set API token
            os.environ["REPLICATE_API_TOKEN"] = self.api_token
            
            # Determine aspect ratio dimensions
            aspect_ratios = {
                "auto": (1024, 1024),
                "1:1": (1024, 1024),
                "9:16": (768, 1344),
                "16:9": (1344, 768),
                "21:9": (1536, 640)
            }
            width, height = aspect_ratios.get(request.aspect_ratio.value, (1024, 1024))
            
            # Get model based on mode
            model_id = self.models.get(request.mode, self.models["nano-banana"])
            
            await job_manager.update_job(
                job_id,
                progress=30,
                message=f"Sending to Replicate ({request.mode})..."
            )
            
            # Prepare input for Replicate
            input_params = {
                "prompt": request.prompt,
                "width": width,
                "height": height,
            }
            
            # Add reference image if provided (for img2img)
            if reference_images and len(reference_images) > 0:
                # Convert first image to data URI
                img_base64 = base64.b64encode(reference_images[0]).decode("utf-8")
                input_params["image"] = f"data:image/png;base64,{img_base64}"
                input_params["strength"] = request.strength
            
            # Add negative prompt for better quality
            input_params["negative_prompt"] = "blurry, low quality, distorted, deformed, ugly, bad anatomy"
            
            await job_manager.update_job(
                job_id,
                progress=50,
                message="Generating face with AI..."
            )
            
            # Run the model on Replicate
            try:
                output = await asyncio.to_thread(
                    replicate.run,
                    model_id,
                    input=input_params
                )
            except replicate.exceptions.ModelError as e:
                # Try fallback model if primary fails
                logger.warning(f"Primary model failed, trying fallback: {e}")
                output = await asyncio.to_thread(
                    replicate.run,
                    "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
                    input={
                        "prompt": request.prompt,
                        "width": width,
                        "height": height,
                        "negative_prompt": "blurry, low quality, distorted"
                    }
                )
            
            await job_manager.update_job(
                job_id,
                progress=80,
                message="Downloading result..."
            )
            
            # Get the output URL
            if isinstance(output, list):
                result_url = output[0] if output else None
            else:
                result_url = output
            
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
                raise Exception("No result URL received from Replicate")
                    
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
