"""
app/models/__init__.py — Import all models so Alembic autogenerates migrations correctly.
"""
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.match import MatchResult
from app.models.skill import Skill
from app.models.recruiter import Recruiter

__all__ = ["Candidate", "Job", "MatchResult", "Skill", "Recruiter"] # noqa: F401
