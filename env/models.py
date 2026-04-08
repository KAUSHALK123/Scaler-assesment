# env/models.py
from pydantic import BaseModel, Field
from typing import Any, Optional
from enum import Enum


class DifficultyLevel(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class TaskInfo(BaseModel):
    task_id: str
    difficulty: DifficultyLevel
    description: str
    schema_description: str
    broken_query: str
    hint: Optional[str] = None


class Observation(BaseModel):
    task_id: str
    step: int
    schema_description: str
    broken_query: str
    last_action: Optional[str] = None
    last_result: Optional[str] = None   # query output or error message
    last_error: Optional[str] = None
    hint: Optional[str] = None
    done: bool = False


class Action(BaseModel):
    sql_query: str = Field(
        ...,
        description="The corrected or optimized SQL query the agent submits"
    )


class Reward(BaseModel):
    value: float = Field(..., ge=0.0, le=1.0)
    breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Partial credit breakdown: syntax, schema, rows, exact"
    )
    message: str = ""


class StepResult(BaseModel):
    observation: Observation
    reward: Reward
    done: bool
    info: dict[str, Any] = Field(default_factory=dict)


class EnvironmentState(BaseModel):
    task_id: str
    step: int
    max_steps: int
    done: bool
    current_observation: Observation
    total_reward: float