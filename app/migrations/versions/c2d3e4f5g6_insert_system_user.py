"""Insert system user for system recruiter"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime, timezone

revision: str = 'c2d3e4f5g6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    system_user_id = uuid.UUID('00000000-0000-0000-0000-000000000001')
    dummy_hash = "!"
    now = datetime.now(timezone.utc)
    op.execute(
        f"INSERT INTO users (id, email, hashed_password, is_active, created_at, updated_at) "
        f"VALUES ('{system_user_id}', 'system@resumeranker.local', '{dummy_hash}', false, '{now}', '{now}') "
        f"ON CONFLICT (email) DO NOTHING"
    )

def downgrade() -> None:
    op.execute("DELETE FROM users WHERE email = 'system@resumeranker.local'")
