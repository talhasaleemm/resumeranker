"""
app/api/v1/auth.py — Authentication endpoints.
"""
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from app.rate_limiter import limiter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import get_db
from app.models.recruiter import Recruiter
from app.schemas.auth import RecruiterCreate, RecruiterResponse, Token
from app.services.auth_service import (
    get_password_hash,
    verify_password,
    get_user_by_email,
    create_access_token,
)

router = APIRouter()

@router.post("/register", response_model=RecruiterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    recruiter_in: RecruiterCreate, session: AsyncSession = Depends(get_db)
) -> Recruiter:
    """Register a new recruiter."""
    existing_user = await get_user_by_email(session, recruiter_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    hashed_password = get_password_hash(recruiter_in.password)
    new_recruiter = Recruiter(
        email=recruiter_in.email,
        hashed_password=hashed_password,
    )
    session.add(new_recruiter)
    try:
        await session.commit()
        await session.refresh(new_recruiter)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    return new_recruiter

@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: AsyncSession = Depends(get_db)
) -> Token:
    """Login to get an access token."""
    user = await get_user_by_email(session, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    settings = get_settings()
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token, token_type="bearer")
