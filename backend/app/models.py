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
    PORTRAIT = "9:16"
    LANDSCAPE = "16:9"
    WIDE = "21:9"


# ================== Face Generation ==================

class FaceGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Description of the face to generate")
    aspect_ratio: AspectRatio = AspectRatio.AUTO
    mode: str = Field(default="nano-banana", description="Generation mode")
    strength: float = Field(default=0.7, ge=0.0, le=1.0, description="Transformation strength")


class FaceGenerationResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime
    result_url: Optional[str] = None
    cost_credits: int = 50


# ================== Video Generation ==================

class MotionType(str, Enum):
    NATURAL = "natural"
    DYNAMIC = "dynamic"
    SUBTLE = "subtle"
    TALKING = "talking"


class VideoGenerationRequest(BaseModel):
    motion_type: MotionType = MotionType.NATURAL
    duration_seconds: int = Field(default=5, ge=2, le=10)
    motion_prompt: Optional[str] = Field(None, description="Optional motion description")
    aspect_ratio: AspectRatio = AspectRatio.PORTRAIT


class VideoGenerationResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime
    result_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    cost_credits: int = 100


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
    cost_credits: int = 75


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

