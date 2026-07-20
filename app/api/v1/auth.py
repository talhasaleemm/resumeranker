"""
app/api/v1/auth.py - Authentication endpoints.
"""
import os
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.rate_limiter import limiter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.recruiter import Recruiter
from app.schemas.auth import UserCreate, UserResponse, Token
from app.services.auth_service import (
    get_password_hash,
    verify_password,
    get_user_by_email,
    create_access_token,
)
from app.worker import ingest_candidate_task

router = APIRouter()

DEMO_RESUME_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "tests", "sample_resumes", "resume_backend_engineer.pdf"
)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    user_in: UserCreate, session: AsyncSession = Depends(get_db)
) -> User:
    """Register a new user and create an associated recruiter tenant.
    Also auto-ingests a demo resume so the user can immediately test matching.
    """
    existing_user = await get_user_by_email(session, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    hashed_password = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
    )
    session.add(new_user)
    try:
        await session.commit()
        await session.refresh(new_user)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_recruiter = Recruiter(
        email=new_user.email,
        hashed_password=hashed_password,
        is_active=True,
    )
    session.add(new_recruiter)
    try:
        await session.commit()
        await session.refresh(new_recruiter)
    except IntegrityError:
        await session.rollback()
        # Recruiter already exists (race) - that's fine, continue.

    # Auto-ingest a demo resume for the new user so they have data to match against.
    if os.path.exists(DEMO_RESUME_PATH):
        try:
            ingest_candidate_task.delay(
                file_path=DEMO_RESUME_PATH,
                original_filename=os.path.basename(DEMO_RESUME_PATH),
                owner_id=str(new_user.id),
            )
        except Exception:
            # Non-blocking: if the task queue is unavailable, the user can still
            # upload resumes manually.
            pass

    return new_user


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
