"""
app/schemas/auth.py — Pydantic schemas for Authentication.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class RecruiterCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

class RecruiterResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None
