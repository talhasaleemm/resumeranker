"""
app/api/v1/tasks.py — Task status polling endpoint (Phase 9).

Allows clients to check the status of background Celery tasks
submitted by the async API endpoints.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.schemas.responses import TaskResponse
from app.worker import celery_app

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """
    Retrieve the status and result of a background task by task_id.

    States:
      - PENDING: task is queued or running
      - SUCCESS: task completed successfully
      - FAILURE: task failed
      - RETRY: task is being retried
      - REVOKED: task was cancelled
    """
    result = celery_app.AsyncResult(task_id)

    if result.state == "PENDING":
        response = {
            "task_id": task_id,
            "status": "pending",
            "result": None,
        }
    elif result.state == "SUCCESS":
        response = {
            "task_id": task_id,
            "status": "success",
            "result": result.result,
        }
    elif result.state == "FAILURE":
        response = {
            "task_id": task_id,
            "status": "failure",
            "result": {
                "error": str(result.result),
            },
        }
    else:
        response = {
            "task_id": task_id,
            "status": result.state.lower(),
            "result": result.result if result.ready() else None,
        }

    return JSONResponse(content=response)
