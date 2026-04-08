# SQL Debug & Optimize Environment

An OpenEnv-compliant AI agent training environment where agents learn to
debug and optimize SQL queries across three difficulty levels.

## Motivation

SQL debugging is a task every data engineer and backend developer does daily.
This environment trains agents to identify and fix syntax errors, logic bugs,
and performance issues in SQL queries — a genuine real-world skill.

## Tasks

| Task ID | Difficulty | Description |
|---|---|---|
| task_easy | Easy | Fix syntax errors (SELEC, FORM, WEHRE) in a broken query |
| task_medium | Medium | Fix logic errors — query runs but returns wrong results |
| task_hard | Hard | Rewrite correlated subquery using JOIN + GROUP BY |

## Action Space

The agent submits a single SQL SELECT statement as a string.
```json
{ "sql_query": "SELECT name, email FROM customers WHERE country = 'US'" }
```

## Observation Space
```json
{
  "task_id": "task_easy",
  "step": 1,
  "schema_description": "...",
  "broken_query": "...",
  "last_action": "...",
  "last_result": "...",
  "last_error": null,
  "hint": "...",
  "done": false
}
```

## Reward Function

Dense reward with 4 partial credit checkpoints per step:

| Checkpoint | Score |
|---|---|
| Query runs without error | +0.25 |
| Column names match expected | +0.25 |
| Row count matches expected | +0.25 |
| Exact values and order match | +0.25 |
| Step penalty per wrong attempt | -0.01 |
| Destructive SQL (DROP/DELETE) | 0.00 |

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| /reset | POST | Start new episode, pass task_id |
| /step | POST | Submit SQL query as action |
| /state | GET | Get current environment state |
| /tasks | GET | List all tasks |
| /health | GET | Health check |

## Setup & Usage

### Local
```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/sql-debug-env
cd sql-debug-env
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 7860
```

### Docker
```bash
docker build -t sql-debug-env .
docker run -p 7860:7860 sql-debug-env
```

### Run Baseline Inference
```bash
export HF_TOKEN=your_token_here
export MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct:nscale
export API_BASE_URL=https://router.huggingface.co/v1
export ENV_BASE_URL=http://localhost:7860
python inference.py
```

## Baseline Scores

| Task | Score | Status |
|---|---|---|
| task_easy | 1.0000 | ✅ Solved |
| task_medium | 1.0000 | ✅ Solved |
| task_hard | 0.7500 | ⚠️ Partial |
| **Average** | **0.9167** | |

## Database Schema
```sql
customers(id, name, email, country)
orders(id, customer_id, status, total, created_at)
order_items(id, order_id, product, quantity, unit_price)
```

## Environment Variables

| Variable | Description |
|---|---|
| API_BASE_URL | OpenAI-compatible LLM endpoint |
| MODEL_NAME | Model identifier |
| HF_TOKEN | Hugging Face API token |
| ENV_BASE_URL | URL where this environment is running |