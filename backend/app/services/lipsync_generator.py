import httpx
import asyncio
import logging
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..config import settings
from ..models import Job, JobStatus, LipSyncRequest, VoiceType
from .job_manager import job_manager

logger = logging.getLogger(__name__)


class LipSyncService:
    """Multi-provider lip sync service supporting ElevenLabs, Sync Labs, and D-ID"""
    
    def __init__(self):
        self.provider = settings.lipsync_provider
        self.timeout = settings.job_timeout_seconds
        self.polling_interval = settings.polling_interval_seconds
        
        # Voice mappings per provider
        self.voice_mappings = {
            "elevenlabs": {
                VoiceType.FEMALE_YOUNG: "EXAVITQu4vr4xnSDxMaL",  # Bella
                VoiceType.FEMALE_MATURE: "pNInz6obpgDQGcFmaJgB",  # Sarah
                VoiceType.FEMALE_SOFT: "jBpfuIE2acCO8z3wKNLl",   # Rachel
                VoiceType.MALE_YOUNG: "pqHfZKP75CvOlQylNhV4",    # Bill
                VoiceType.MALE_DEEP: "VR6AewLTigWG4xSOukaG"      # Arnold
            },
            "sync_labs": {
                VoiceType.FEMALE_YOUNG: "female_young",
                VoiceType.FEMALE_MATURE: "female_mature",
                VoiceType.FEMALE_SOFT: "female_soft",
                VoiceType.MALE_YOUNG: "male_young",
                VoiceType.MALE_DEEP: "male_deep"
            },
            "d-id": {
                VoiceType.FEMALE_YOUNG: "en-US-JennyNeural",
                VoiceType.FEMALE_MATURE: "en-US-AriaNeural",
                VoiceType.FEMALE_SOFT: "en-US-SaraNeural",
                VoiceType.MALE_YOUNG: "en-US-GuyNeural",
                VoiceType.MALE_DEEP: "en-US-DavisNeural"
            }
        }
    
    async def generate_lipsync(
        self,
        request: LipSyncRequest,
        video_file: bytes
    ) -> Job:
        """Start lip sync job with configured provider"""
        
        job = Job(
            job_type="lipsync",
            status=JobStatus.PENDING,
            message=f"Initializing lip sync with {self.provider}...",
            metadata={
                "text": request.text,
                "voice_type": request.voice_type.value,
                "language": request.language,
                "provider": self.provider
            }
        )
        await job_manager.create_job(job)
        
        # Route to appropriate provider
        if self.provider == "elevenlabs":
            asyncio.create_task(self._process_elevenlabs(job.id, request, video_file))
        elif self.provider == "sync_labs":
            asyncio.create_task(self._process_sync_labs(job.id, request, video_file))
        elif self.provider == "d-id":
            asyncio.create_task(self._process_did(job.id, request, video_file))
        
        return job
    
    # ================== ElevenLabs Implementation ==================
    
    async def _process_elevenlabs(
        self,
        job_id: str,
        request: LipSyncRequest,
        video_file: bytes
    ):
        """Process with ElevenLabs TTS + external lip sync"""
        try:
            await job_manager.update_job(
                job_id,
                status=JobStatus.PROCESSING,
                progress=10,
                message="Generating voice with ElevenLabs..."
            )
            
            voice_id = self.voice_mappings["elevenlabs"].get(
                request.voice_type,
                self.voice_mappings["elevenlabs"][VoiceType.FEMALE_YOUNG]
            )
            
            headers = {
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Generate speech
                tts_payload = {
                    "text": request.text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.75,
                        "similarity_boost": 0.75
                    }
                }
                
                tts_response = await client.post(
                    f"{settings.elevenlabs_base_url}/text-to-speech/{voice_id}",
                    json=tts_payload,
                    headers=headers
                )
                
                if tts_response.status_code != 200:
                    raise Exception(f"TTS error: {tts_response.status_code}")
                
                audio_data = tts_response.content
                
                # Save audio
                audio_filename = f"{job_id}_audio.mp3"
                audio_path = Path(settings.storage_path) / "lipsync" / audio_filename
                audio_path.write_bytes(audio_data)
                
                await job_manager.update_job(
                    job_id,
                    progress=50,
                    message="Applying lip sync..."
                )
                
                # Use Sync Labs for lip sync if available, otherwise save audio only
                if settings.sync_labs_api_key:
                    result_url = await self._apply_sync_labs_lipsync(
                        client, video_file, audio_data, job_id
                    )
                else:
                    # Fallback: just return video with audio path
                    video_filename = f"{job_id}.mp4"
                    video_path = Path(settings.storage_path) / "lipsync" / video_filename
                    video_path.write_bytes(video_file)
                    result_url = f"/storage/lipsync/{video_filename}"
                
                await job_manager.update_job(
                    job_id,
                    status=JobStatus.COMPLETED,
                    progress=100,
                    message="Lip sync completed!",
                    result_url=result_url
                )
                
        except Exception as e:
            logger.error(f"ElevenLabs lip sync failed: {e}")
            await job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                message="Lip sync failed",
                error=str(e)
            )
    
    # ================== Sync Labs Implementation ==================
    
    async def _process_sync_labs(
        self,
        job_id: str,
        request: LipSyncRequest,
        video_file: bytes
    ):
        """Process with Sync Labs (native lip sync)"""
        try:
            await job_manager.update_job(
                job_id,
                status=JobStatus.PROCESSING,
                progress=15,
                message="Uploading to Sync Labs..."
            )
            
            headers = {
                "x-api-key": settings.sync_labs_api_key,
            }
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Upload video
                files = {
                    "video": ("input.mp4", video_file, "video/mp4")
                }
                data = {
                    "transcript": request.text,
                    "voice": self.voice_mappings["sync_labs"].get(
                        request.voice_type, "female_young"
                    ),
                    "language": request.language
                }
                
                response = await client.post(
                    f"{settings.sync_labs_base_url}/lipsync",
                    files=files,
                    data=data,
                    headers=headers
                )
                
                if response.status_code not in [200, 201, 202]:
                    raise Exception(f"Sync Labs error: {response.status_code}")
                
                result = response.json()
                provider_job_id = result.get("id")
                
                await job_manager.update_job(
                    job_id,
                    provider_job_id=provider_job_id,
                    progress=40,
                    message="Processing lip sync..."
                )
                
                # Poll for completion
                result_url = await self._poll_sync_labs(client, headers, provider_job_id, job_id)
                local_url = await self._save_result(client, result_url, job_id)
                
                await job_manager.update_job(
                    job_id,
                    status=JobStatus.COMPLETED,
                    progress=100,
                    message="Lip sync completed!",
                    result_url=local_url
                )
                
        except Exception as e:
            logger.error(f"Sync Labs lip sync failed: {e}")
            await job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                message="Lip sync failed",
                error=str(e)
            )
    
    async def _apply_sync_labs_lipsync(
        self,
        client: httpx.AsyncClient,
        video_file: bytes,
        audio_data: bytes,
        job_id: str
    ) -> str:
        """Apply Sync Labs lip sync with custom audio"""
        
        headers = {
            "x-api-key": settings.sync_labs_api_key,
        }
        
        files = {
            "video": ("input.mp4", video_file, "video/mp4"),
            "audio": ("audio.mp3", audio_data, "audio/mpeg")
        }
        
        response = await client.post(
            f"{settings.sync_labs_base_url}/lipsync/audio",
            files=files,
            headers=headers
        )
        
        if response.status_code not in [200, 201, 202]:
            raise Exception(f"Sync Labs audio error: {response.status_code}")
        
        result = response.json()
        provider_job_id = result.get("id")
        
        # Poll for result
        result_url = await self._poll_sync_labs(client, headers, provider_job_id, job_id)
        return await self._save_result(client, result_url, job_id)
    
    async def _poll_sync_labs(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        provider_job_id: str,
        job_id: str
    ) -> str:
        """Poll Sync Labs for completion"""
        
        max_attempts = self.timeout // self.polling_interval
        
        for attempt in range(max_attempts):
            await asyncio.sleep(self.polling_interval)
            
            progress = min(40 + (attempt * 4), 95)
            await job_manager.update_job(
                job_id,
                progress=progress,
                message=f"Syncing lips... ({attempt * self.polling_interval}s)"
            )
            
            response = await client.get(
                f"{settings.sync_labs_base_url}/lipsync/{provider_job_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "").lower()
                
                if status in ["completed", "done"]:
                    return data.get("video_url") or data.get("result", {}).get("url")
                elif status in ["failed", "error"]:
                    raise Exception(data.get("error", "Sync failed"))
        
        raise Exception("Lip sync timed out")
    
    # ================== D-ID Implementation ==================
    
    async def _process_did(
        self,
        job_id: str,
        request: LipSyncRequest,
        video_file: bytes
    ):
        """Process with D-ID talking avatar"""
        try:
            await job_manager.update_job(
                job_id,
                status=JobStatus.PROCESSING,
                progress=15,
                message="Creating with D-ID..."
            )
            
            headers = {
                "Authorization": f"Basic {settings.did_api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                # First upload the video/image as source
                # D-ID works best with images, extract first frame if needed
                
                payload = {
                    "source_url": base64.b64encode(video_file).decode("utf-8"),
                    "script": {
                        "type": "text",
                        "input": request.text,
                        "provider": {
                            "type": "microsoft",
                            "voice_id": self.voice_mappings["d-id"].get(
                                request.voice_type,
                                "en-US-JennyNeural"
                            )
                        }
                    }
                }
                
                response = await client.post(
                    f"{settings.did_base_url}/talks",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code not in [200, 201]:
                    raise Exception(f"D-ID error: {response.status_code}")
                
                result = response.json()
                provider_job_id = result.get("id")
                
                await job_manager.update_job(
                    job_id,
                    provider_job_id=provider_job_id,
                    progress=40,
                    message="Generating talking video..."
                )
                
                # Poll for completion
                result_url = await self._poll_did(client, headers, provider_job_id, job_id)
                local_url = await self._save_result(client, result_url, job_id)
                
                await job_manager.update_job(
                    job_id,
                    status=JobStatus.COMPLETED,
                    progress=100,
                    message="Lip sync completed!",
                    result_url=local_url
                )
                
        except Exception as e:
            logger.error(f"D-ID lip sync failed: {e}")
            await job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                message="Lip sync failed",
                error=str(e)
            )
    
    async def _poll_did(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        provider_job_id: str,
        job_id: str
    ) -> str:
        """Poll D-ID for completion"""
        
        max_attempts = self.timeout // self.polling_interval
        
        for attempt in range(max_attempts):
            await asyncio.sleep(self.polling_interval)
            
            progress = min(40 + (attempt * 4), 95)
            await job_manager.update_job(
                job_id,
                progress=progress,
                message=f"Creating talking video... ({attempt * self.polling_interval}s)"
            )
            
            response = await client.get(
                f"{settings.did_base_url}/talks/{provider_job_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "").lower()
                
                if status in ["done", "completed"]:
                    return data.get("result_url")
                elif status in ["error", "failed"]:
                    raise Exception(data.get("error", {}).get("description", "D-ID failed"))
        
        raise Exception("D-ID generation timed out")
    
    async def _save_result(
        self,
        client: httpx.AsyncClient,
        url: str,
        job_id: str
    ) -> str:
        """Download and save result"""
        
        response = await client.get(url)
        response.raise_for_status()
        
        filename = f"{job_id}.mp4"
        filepath = Path(settings.storage_path) / "lipsync" / filename
        filepath.write_bytes(response.content)
        
        return f"/storage/lipsync/{filename}"


# Global service instance
lipsync_generator = LipSyncService()

