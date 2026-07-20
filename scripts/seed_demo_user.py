"""
scripts/seed_demo_user.py — Idempotently seed a demo User for local dev login.

Uses the application's own passlib (argon2) context and async DB session so the
stored hash matches what auth_service.verify_password expects at login time.

Run inside the backend container:
    docker exec -it resumeranker-app-1 python scripts/seed_demo_user.py
"""
import asyncio

from app.database import AsyncSessionLocal
from app.models.user import User
from app.services.auth_service import get_password_hash
from sqlalchemy import select


DEMO_EMAIL = "demo@resumeranker.com"
DEMO_PASSWORD = "demo1234"


async def main() -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(User).where(User.email == DEMO_EMAIL))
        if existing.scalars().first() is not None:
            print(f"[seed] User {DEMO_EMAIL} already exists — skipping.")
            return

        user = User(
            email=DEMO_EMAIL,
            hashed_password=get_password_hash(DEMO_PASSWORD),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"[seed] Created demo User {DEMO_EMAIL} (active).")


if __name__ == "__main__":
    asyncio.run(main())
