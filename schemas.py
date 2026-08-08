from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class UserRegisterSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Passwords do not match')
        return v


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class OTPVerifySchema(BaseModel):
    otp_code: str = Field(..., pattern=r'^\d{6}$')


class ProductCreateSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=10)
    price: float = Field(..., ge=0, le=10000)
    rating: float = Field(default=4.8, ge=1.0, le=5.0)
    tags: str = Field(default="", max_length=500)


class ProductUpdateSchema(ProductCreateSchema):
    product_id: int = Field(..., gt=0)


class ChatMessageSchema(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class EventTrackSchema(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    event_type: str = Field(..., min_length=1, max_length=50)
    target_id: Optional[str] = Field(None, max_length=100)
    details: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = Field(default=0, ge=0)


class EventBatchSchema(BaseModel):
    events: List[EventTrackSchema] = Field(..., min_length=1, max_length=50)


class RecommendationRefreshSchema(BaseModel):
    session_id: str = Field(default="sess_manual", max_length=100)


class AdminTriggerDigestSchema(BaseModel):
    user_id: int = Field(..., gt=0)