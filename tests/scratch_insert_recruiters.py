import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from app.config import get_settings

async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine) as session:
        await session.execute(text(
            "INSERT INTO recruiters (id, email, hashed_password, is_active, created_at, updated_at) "
            "VALUES ('00000000-0000-0000-0000-000000000000', 'test000@resumeranker.local', '...', true, NOW(), NOW()) "
            "ON CONFLICT (id) DO NOTHING"
        ))
        await session.execute(text(
            "INSERT INTO recruiters (id, email, hashed_password, is_active, created_at, updated_at) "
            "VALUES ('00000000-0000-0000-0000-000000000001', 'test@test.com', '...', true, NOW(), NOW()) "
            "ON CONFLICT (id) DO NOTHING"
        ))
        await session.commit()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
