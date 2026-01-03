from pydantic_settings import BaseSettings
from typing import Literal
import os


class Settings(BaseSettings):
    # Replicate API (for Face & Video generation)
    replicate_api_token: str = ""
    
    # Face Generation Model (on Replicate)
    # Recommended default (official Replicate model)
    face_model: str = "google/nano-banana-pro:eefce837d77048ccc736cd660d4f178d223b2d99aeb5ef856741eb81941c9ed2"
    
    # Video Generation Model (on Replicate)  
    # Default: Kling v2.6 Motion Control (image + driving video -> video)
    #
    # Use the MODEL SLUG (no pinned version) to avoid "Invalid version" errors for models that
    # have hidden/rolling versions or gated version IDs.
    video_model: str = "kwaivgi/kling-v2.6-motion-control"
    
    # Lip Sync Provider
    lipsync_provider: Literal["elevenlabs", "sync_labs", "d-id"] = "elevenlabs"
    
    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_base_url: str = "https://api.elevenlabs.io/v1"
    
    # Sync Labs
    sync_labs_api_key: str = ""
    sync_labs_base_url: str = "https://api.synclabs.so/v2"
    
    # D-ID
    did_api_key: str = ""
    did_base_url: str = "https://api.d-id.com"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # Storage
    storage_path: str = "./storage"
    max_file_size_mb: int = 50
    
    # Job Configuration
    # Replicate jobs can take several minutes depending on queue/load.
    job_timeout_seconds: int = 900
    polling_interval_seconds: int = 5
    max_retries: int = 3
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure storage directories exist
os.makedirs(settings.storage_path, exist_ok=True)
os.makedirs(f"{settings.storage_path}/faces", exist_ok=True)
os.makedirs(f"{settings.storage_path}/videos", exist_ok=True)
os.makedirs(f"{settings.storage_path}/lipsync", exist_ok=True)
os.makedirs(f"{settings.storage_path}/uploads", exist_ok=True)
