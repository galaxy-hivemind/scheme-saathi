"""
Authentication request and response schemas.
"""
from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    preferred_language: str = Field(default="hi", pattern="^(hi|en)$")

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        byte_len = len(v.encode("utf-8"))
        if byte_len > 72:
            raise ValueError(f"Password cannot exceed 72 bytes in UTF-8 encoding (got {byte_len} bytes).")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        byte_len = len(v.encode("utf-8"))
        if byte_len > 72:
            raise ValueError(f"Password cannot exceed 72 bytes in UTF-8 encoding (got {byte_len} bytes).")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user_id: uuid.UUID
    email: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_active: bool
    created_at: datetime
