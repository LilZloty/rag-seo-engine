from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult
from app.celery_app import celery
from app.core.config import settings

router = APIRouter()


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a Celery task by ID."""
    if not settings.USE_CELERY:
        raise HTTPException(status_code=501, detail="Celery is not enabled")

    result = AsyncResult(task_id, app=celery)

    response = {
        "task_id": task_id,
        "status": result.status,
        "result": None,
        "progress": None,
    }

    if result.status == "PROGRESS":
        response["progress"] = result.info
    elif result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["result"] = str(result.result)

    return response


@router.get("/tasks")
async def list_active_tasks():
    """List active Celery tasks."""
    if not settings.USE_CELERY:
        raise HTTPException(status_code=501, detail="Celery is not enabled")

    inspect = celery.control.inspect()
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}

    tasks = []
    for worker, worker_tasks in active.items():
        for t in worker_tasks:
            tasks.append({
                "task_id": t["id"],
                "name": t["name"],
                "worker": worker,
                "status": "active",
            })
    for worker, worker_tasks in reserved.items():
        for t in worker_tasks:
            tasks.append({
                "task_id": t["id"],
                "name": t["name"],
                "worker": worker,
                "status": "reserved",
            })

    return {"tasks": tasks, "count": len(tasks)}
