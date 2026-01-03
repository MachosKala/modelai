from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum
from datetime import datetime
import uuid


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AspectRatio(str, Enum):
    AUTO = "auto"
    SQUARE = "1:1"
    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"
    RATIO_4_3 = "4:3"
    RATIO_3_4 = "3:4"
    RATIO_9_21 = "9:21"
    RATIO_21_9 = "21:9"
    RATIO_2_3 = "2:3"
    RATIO_3_2 = "3:2"


# ================== Face Generation ==================

class FaceGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Description of the face to generate")
    aspect_ratio: AspectRatio = AspectRatio.AUTO


class FaceGenerationResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime
    result_url: Optional[str] = None


# ================== Video Generation ==================

class VideoAspectRatio(str, Enum):
    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"


class VideoGenerationRequest(BaseModel):
    mode: Optional[str] = Field(default=None, description="Optional model mode (model-specific)")
    prompt: str = Field(default="", description="Prompt for the video generation")
    aspect_ratio: VideoAspectRatio = VideoAspectRatio.LANDSCAPE


class VideoGenerationResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime
    result_url: Optional[str] = None
    provider: Optional[str] = None


# ================== Lip Sync ==================

class VoiceType(str, Enum):
    FEMALE_YOUNG = "female_young"
    FEMALE_MATURE = "female_mature"
    FEMALE_SOFT = "female_soft"
    MALE_YOUNG = "male_young"
    MALE_DEEP = "male_deep"


class LipSyncRequest(BaseModel):
    text: str = Field(..., description="Text to speak")
    voice_type: VoiceType = VoiceType.FEMALE_YOUNG
    language: str = Field(default="en", description="Language code (en, it, es, etc.)")


class LipSyncResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime
    result_url: Optional[str] = None
    audio_url: Optional[str] = None


# ================== Job Status ==================

class JobStatusResponse(BaseModel):
    job_id: str
    job_type: Literal["face", "video", "lipsync"]
    status: JobStatus
    progress: int = Field(default=0, ge=0, le=100)
    message: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result_url: Optional[str] = None
    error: Optional[str] = None


# ================== Job Storage ==================

class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_type: Literal["face", "video", "lipsync"]
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    message: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    result_url: Optional[str] = None
    error: Optional[str] = None
    provider_job_id: Optional[str] = None
    input_files: List[str] = []
    metadata: dict = {}

