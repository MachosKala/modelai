import replicate
import asyncio
import logging
import base64
import httpx
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..config import settings
from ..models import Job, JobStatus, VideoGenerationRequest
from .job_manager import job_manager

logger = logging.getLogger(__name__)


class ReplicateVideoService:
    """Service for video generation using Replicate API with Kling v2.6 Motion Control"""
    
    def __init__(self):
        self.api_token = settings.replicate_api_token
        # Available video generation models on Replicate
        self.models = {
            "kling": "klingai/kling-v2-master",  # Kling model if available
            "svd": "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",
            "animate": "lucataco/animate-diff:beecf59c4aee8d81bf04f0381033dfa10dc16e845b4ae00d281e2fa377e48571",
            "minimax": "minimax/video-01",
            "wan": "wan-video/wan-2.1"
        }
        self.timeout = settings.job_timeout_seconds
    
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
        """Process video generation in background using Replicate"""
        try:
            await job_manager.update_job(
                job_id,
                status=JobStatus.PROCESSING,
                progress=10,
                message="Preparing video request..."
            )
            
            # Set API token
            os.environ["REPLICATE_API_TOKEN"] = self.api_token
            
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
                message="Sending to Replicate for video generation..."
            )
            
            # Try Kling model first, then fallback to Stable Video Diffusion
            video_url = None
            
            # Primary: Try Stable Video Diffusion (most reliable)
            try:
                await job_manager.update_job(
                    job_id,
                    progress=40,
                    message="Generating video with AI..."
                )
                
                # Use Stable Video Diffusion
                output = await asyncio.to_thread(
                    replicate.run,
                    self.models["svd"],
                    input={
                        "input_image": image_uri,
                        "motion_bucket_id": 127 if request.motion_type.value == "dynamic" else 80,
                        "fps": 7,
                        "cond_aug": 0.02,
                        "decoding_t": 7,
                        "video_length": "14_frames_with_svd" if request.duration_seconds <= 3 else "25_frames_with_svd_xt"
                    }
                )
                
                if output:
                    video_url = output if isinstance(output, str) else output[0] if isinstance(output, list) else None
                    
            except Exception as e:
                logger.warning(f"SVD failed, trying AnimateDiff: {e}")
                
                # Fallback: AnimateDiff
                try:
                    output = await asyncio.to_thread(
                        replicate.run,
                        self.models["animate"],
                        input={
                            "image": image_uri,
                            "prompt": motion_prompt,
                            "n_prompt": "blurry, distorted, low quality",
                            "steps": 25,
                            "guidance_scale": 7.5
                        }
                    )
                    
                    if output:
                        video_url = output if isinstance(output, str) else output[0] if isinstance(output, list) else None
                        
                except Exception as e2:
                    logger.error(f"AnimateDiff also failed: {e2}")
                    raise Exception(f"Video generation failed: {e2}")
            
            if not video_url:
                raise Exception("No video URL received from Replicate")
            
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
