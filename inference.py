# inference.py
"""
Baseline inference script for SQL Debug & Optimize Environment.
Judges will run this directly. Do not rename.

Required environment variables:
    API_BASE_URL  — OpenAI-compatible endpoint (e.g. HF Inference API)
    MODEL_NAME    — Model identifier
    HF_TOKEN      — Hugging Face API token
"""

import os
import json
import time
import requests
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────
# CONFIG — read from environment variables
# ─────────────────────────────────────────────

API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "Qwen/Qwen2.5-Coder-32B-Instruct:nscale")
HF_TOKEN     = os.environ.get("HF_TOKEN",     "")

# Local server (where FastAPI is running)
ENV_BASE_URL = os.environ.get("ENV_BASE_URL", "http://localhost:7860")

TEMPERATURE  = 0.1
MAX_TOKENS   = 512
MAX_STEPS    = 5   # max attempts per task in inference

TASKS = ["task_easy", "task_medium", "task_hard"]


# ─────────────────────────────────────────────
# OPENAI CLIENT — pointed at HF Inference API
# ─────────────────────────────────────────────

client = OpenAI(
    api_key=HF_TOKEN,
    base_url=API_BASE_URL,
)


# ─────────────────────────────────────────────
# ENV API HELPERS
# ─────────────────────────────────────────────

def env_reset(task_id: str) -> dict:
    resp = requests.post(
        f"{ENV_BASE_URL}/reset",
        json={"task_id": task_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def env_step(sql_query: str) -> dict:
    resp = requests.post(
        f"{ENV_BASE_URL}/step",
        json={"sql_query": sql_query},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def env_state() -> dict:
    resp = requests.get(f"{ENV_BASE_URL}/state", timeout=30)
    resp.raise_for_status()
    return resp.json()


# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert SQL developer and debugger.
You will be given a broken or inefficient SQL query and a database schema.
Your job is to fix or optimize the query.

Rules:
- Return ONLY the corrected SQL query, nothing else
- No explanations, no markdown, no code fences
- No destructive statements (DROP, DELETE, UPDATE, INSERT, ALTER)
- The query must be valid SQLite syntax
- Output must be a single SELECT statement
"""


# ─────────────────────────────────────────────
# AGENT LOOP
# ─────────────────────────────────────────────

def build_prompt(observation: dict, attempt: int) -> str:
    prompt = f"""Task: {observation['task_id']}
Attempt: {attempt}

Database Schema:
{observation['schema_description']}

Broken/Inefficient Query to fix:
{observation['broken_query']}

Task Description is to fix the query so it works correctly and efficiently.
"""
    if observation.get("last_result"):
        prompt += f"\nYour last query returned:\n{observation['last_result']}"
    if observation.get("last_error"):
        prompt += f"\nYour last query had this error:\n{observation['last_error']}"
    if observation.get("hint"):
        prompt += f"\nHint: {observation['hint']}"

    prompt += "\n\nReturn ONLY the corrected SQL query:"
    return prompt


def run_task(task_id: str) -> dict:
    """Run one full episode for a task. Returns result summary."""
    print(f"\n{'='*50}")
    print(f"  TASK: {task_id.upper()}")
    print(f"{'='*50}")

    observation = env_reset(task_id)
    print(f"  Broken query:\n  {observation['broken_query']}\n")

    best_score = 0.0
    final_result = {}

    for attempt in range(1, MAX_STEPS + 1):
        print(f"  [Attempt {attempt}/{MAX_STEPS}]")

        # Build prompt from current observation
        user_prompt = build_prompt(observation, attempt)

        # Call LLM via OpenAI client
        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            sql_query = completion.choices[0].message.content.strip()
        except Exception as exc:
            print(f"  LLM call failed: {exc}")
            sql_query = observation["broken_query"]  # fallback

        # Clean up common LLM formatting issues
        sql_query = _clean_sql(sql_query)
        print(f"  Submitted: {sql_query[:80]}{'...' if len(sql_query)>80 else ''}")

        # Step the environment
        result = env_step(sql_query)
        reward  = result["reward"]["value"]
        done    = result["done"]
        breakdown = result["reward"]["breakdown"]
        message   = result["reward"]["message"]

        print(f"  Score: {reward:.4f} | {message}")
        print(f"  Breakdown: {breakdown}")

        best_score = max(best_score, reward)
        observation = result["observation"]
        final_result = result

        if done:
            if reward == 1.0:
                print(f"  ✅ SOLVED in {attempt} attempt(s)!")
            else:
                print(f"  ❌ Episode ended. Best score: {best_score:.4f}")
            break

        time.sleep(0.5)  # be kind to the API

    return {
        "task_id": task_id,
        "best_score": best_score,
        "attempts": attempt,
        "solved": best_score == 1.0,
    }


def _clean_sql(text: str) -> str:
    """Strip markdown fences and whitespace LLMs commonly add."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("\n🚀 SQL Debug & Optimize Environment — Baseline Inference")
    print(f"   Model:    {MODEL_NAME}")
    print(f"   Endpoint: {API_BASE_URL}")
    print(f"   Env:      {ENV_BASE_URL}\n")

    if not HF_TOKEN:
        print("⚠️  WARNING: HF_TOKEN is not set. LLM calls will likely fail.")

    results = []
    total_start = time.time()

    for task_id in TASKS:
        task_result = run_task(task_id)
        results.append(task_result)

    total_time = time.time() - total_start

    # ── Final Score Report ──
    print(f"\n{'='*50}")
    print("  FINAL RESULTS")
    print(f"{'='*50}")
    for r in results:
        status = "✅ SOLVED" if r["solved"] else "❌ FAILED"
        print(f"  {r['task_id']:<15} score={r['best_score']:.4f}  {status}  attempts={r['attempts']}")

    avg_score = sum(r["best_score"] for r in results) / len(results)
    print(f"\n  Average Score : {avg_score:.4f}")
    print(f"  Total Time    : {total_time:.1f}s")
    print(f"{'='*50}\n")

    # Save results to JSON for reproducibility
    output = {
        "model": MODEL_NAME,
        "endpoint": API_BASE_URL,
        "results": results,
        "average_score": avg_score,
        "total_time_seconds": round(total_time, 2),
    }
    with open("baseline_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print("  Results saved to baseline_results.json")


if __name__ == "__main__":
    main()