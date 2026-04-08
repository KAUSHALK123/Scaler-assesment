# main.py
import sys
import os

# Ensure the app directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
from pydantic import BaseModel

from env.environment import SQLDebugEnvironment
from env.models import Action, StepResult, EnvironmentState, Observation
from env.tasks import TASKS


# ─────────────────────────────────────────────
# APP LIFECYCLE
# ─────────────────────────────────────────────

env = SQLDebugEnvironment()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown — clean up DB connection
    env.close()


app = FastAPI(
    title="SQL Debug & Optimize Environment",
    description=(
        "An OpenEnv-compliant environment where AI agents learn to debug "
        "and optimize SQL queries. 3 tasks: easy (syntax fix), "
        "medium (logic fix), hard (optimization)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────

class ResetRequest(BaseModel):
    task_id: Optional[str] = "task_easy"


class StepRequest(BaseModel):
    sql_query: str


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.get("/")
def root():
    """Health check — HF Spaces ping endpoint."""
    return {
        "status": "ok",
        "environment": "sql-debug-env",
        "version": "1.0.0",
        "tasks": list(TASKS.keys()),
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# ─────────────────────────────────────────────
# OPENENV CORE ENDPOINTS
# ─────────────────────────────────────────────

@app.post("/reset", response_model=Observation)
def reset(request: Optional[ResetRequest] = None):
    """
    Reset the environment and start a new episode.
    Accepts optional JSON body with task_id:
    'task_easy' | 'task_medium' | 'task_hard'.
    If body is omitted, defaults to 'task_easy'.
    """
    try:
        task_id = request.task_id if request is not None else "task_easy"
        obs = env.reset(task_id=task_id)
        return obs
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/step", response_model=StepResult)
def step(request: StepRequest):
    """
    Submit a SQL query as an action.
    Returns observation, reward, done, info.
    """
    try:
        action = Action(sql_query=request.sql_query)
        result = env.step(action)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/state", response_model=EnvironmentState)
def state():
    """
    Get the current full state of the environment.
    """
    try:
        return env.state()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# EXTRA UTILITY ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/tasks")
def list_tasks():
    """List all available tasks with descriptions."""
    return {
        task_id: {
            "difficulty": task.difficulty,
            "description": task.description,
            "hint": task.hint,
        }
        for task_id, task in TASKS.items()
    }


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    """Get full details of a specific task."""
    if task_id not in TASKS:
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_id}' not found. Valid: {list(TASKS.keys())}"
        )
    task = TASKS[task_id]
    return {
        "task_id": task.task_id,
        "difficulty": task.difficulty,
        "description": task.description,
        "schema_description": task.schema_description,
        "broken_query": task.broken_query,
        "hint": task.hint,
    }