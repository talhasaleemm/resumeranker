"""
app/models/__init__.py — Import all models so Alembic autogenerates migrations correctly.
"""
from app.models.candidate import Candidate  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.match import MatchResult  # noqa: F401
