from pydantic_settings import BaseSettings
from typing import Literal
import os


class Settings(BaseSettings):
    # Replicate API (for Face & Video generation)
    replicate_api_token: str = ""
    
    # Face Generation Model (on Replicate)
    face_model: str = "nanobanana/nano-banana-pro"
    
    # Video Generation Model (on Replicate)  
    video_model: str = "klingai/kling-v2.6-motion-control"
    
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
    job_timeout_seconds: int = 300
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
