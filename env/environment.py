# env/environment.py
import uuid
from typing import Optional
from env.models import (
    Observation,
    Action,
    Reward,
    StepResult,
    EnvironmentState,
)
from env.tasks import TASKS, grade, get_connection, setup_ecommerce_db, run_query


MAX_STEPS = 10
# Penalty applied per step to encourage efficiency
STEP_PENALTY = 0.01


class SQLDebugEnvironment:
    """
    OpenEnv-compliant environment for SQL debugging and optimization.
    One episode = one task. Agent submits SQL queries until correct or max_steps reached.
    """

    def __init__(self) -> None:
        self._session_id: str = str(uuid.uuid4())
        self._task_id: Optional[str] = None
        self._step: int = 0
        self._done: bool = False
        self._total_reward: float = 0.0
        self._last_observation: Optional[Observation] = None
        self._conn = None  # SQLite connection lives for the episode

    # ─────────────────────────────────────────
    # RESET
    # ─────────────────────────────────────────

    def reset(self, task_id: Optional[str] = None) -> Observation:
        """
        Start a fresh episode.
        If task_id is None, defaults to task_easy.
        Returns the initial Observation.
        """
        # Validate task_id
        if task_id is None:
            task_id = "task_easy"
        if task_id not in TASKS:
            raise ValueError(
                f"Unknown task_id '{task_id}'. "
                f"Valid options: {list(TASKS.keys())}"
            )

        # Close any existing connection
        if self._conn is not None:
            self._conn.close()

        # Fresh state
        self._session_id = str(uuid.uuid4())
        self._task_id = task_id
        self._step = 0
        self._done = False
        self._total_reward = 0.0

        # Fresh DB for this episode
        self._conn = get_connection()
        setup_ecommerce_db(self._conn)

        task = TASKS[task_id]

        obs = Observation(
            task_id=task_id,
            step=0,
            schema_description=task.schema_description,
            broken_query=task.broken_query,
            last_action=None,
            last_result=None,
            last_error=None,
            hint=task.hint,
            done=False,
        )
        self._last_observation = obs
        return obs

    # ─────────────────────────────────────────
    # STEP
    # ─────────────────────────────────────────

    def step(self, action: Action) -> StepResult:
        """
        Agent submits a SQL query.
        Returns StepResult(observation, reward, done, info).
        """
        if self._done:
            raise RuntimeError(
                "Episode is already done. Call reset() to start a new episode."
            )
        if self._task_id is None:
            raise RuntimeError(
                "Environment not initialized. Call reset() first."
            )

        self._step += 1
        submitted_sql = action.sql_query.strip()

        # ── Run the submitted query to get live feedback ──
        rows, error = run_query(submitted_sql, self._conn)

        # ── Grade the submission ──
        raw_score, breakdown, grade_message = grade(self._task_id, submitted_sql)

        # ── Apply step penalty to encourage solving early ──
        # Penalty only if not perfect — we don't penalize a correct first-try
        step_penalty = 0.0
        if raw_score < 1.0:
            step_penalty = STEP_PENALTY * self._step
        
        penalized_score = max(0.0, round(raw_score - step_penalty, 4))

        # ── Check done conditions ──
        # Done if: perfect score OR max steps reached OR destructive SQL attempted
        is_perfect = raw_score == 1.0
        max_steps_reached = self._step >= MAX_STEPS
        is_destructive = _is_destructive(submitted_sql)

        if is_destructive:
            # Hard penalty for destructive actions
            penalized_score = 0.0
            breakdown = {k: 0.0 for k in breakdown}
            grade_message = "Destructive SQL detected (DROP/DELETE/UPDATE). Score zeroed."

        self._done = is_perfect or max_steps_reached or is_destructive
        self._total_reward += penalized_score

        # ── Build result string for observation ──
        if error:
            result_str = f"ERROR: {error}"
        elif rows:
            result_str = _rows_to_str(rows[:5])  # show max 5 rows
        else:
            result_str = "Query returned 0 rows."

        obs = Observation(
            task_id=self._task_id,
            step=self._step,
            schema_description=TASKS[self._task_id].schema_description,
            broken_query=TASKS[self._task_id].broken_query,
            last_action=submitted_sql,
            last_result=result_str,
            last_error=error,
            hint=TASKS[self._task_id].hint,
            done=self._done,
        )
        self._last_observation = obs

        reward = Reward(
            value=penalized_score,
            breakdown=breakdown,
            message=grade_message,
        )

        info = {
            "session_id": self._session_id,
            "raw_score": raw_score,
            "step_penalty": step_penalty,
            "total_reward_so_far": round(self._total_reward, 4),
            "is_perfect": is_perfect,
            "max_steps_reached": max_steps_reached,
        }

        return StepResult(
            observation=obs,
            reward=reward,
            done=self._done,
            info=info,
        )

    # ─────────────────────────────────────────
    # STATE
    # ─────────────────────────────────────────

    def state(self) -> EnvironmentState:
        """
        Returns the full current state of the environment.
        """
        if self._task_id is None or self._last_observation is None:
            raise RuntimeError(
                "Environment not initialized. Call reset() first."
            )
        return EnvironmentState(
            task_id=self._task_id,
            step=self._step,
            max_steps=MAX_STEPS,
            done=self._done,
            current_observation=self._last_observation,
            total_reward=round(self._total_reward, 4),
        )

    # ─────────────────────────────────────────
    # CLEANUP
    # ─────────────────────────────────────────

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _is_destructive(sql: str) -> bool:
    """Penalize any attempt to mutate or destroy the DB."""
    upper = sql.upper()
    destructive_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
    return any(kw in upper for kw in destructive_keywords)


def _rows_to_str(rows: list[dict]) -> str:
    """Format query result rows as a readable string for the observation."""
    if not rows:
        return "No rows returned."
    headers = list(rows[0].keys())
    lines = [" | ".join(headers)]
    lines.append("-" * len(lines[0]))
    for row in rows:
        lines.append(" | ".join(str(v) for v in row.values()))
    return "\n".join(lines)