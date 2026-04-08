---
title: SQL Debug & Optimize Environment
emoji: 🔍
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# SQL Debug & Optimize Environment

An OpenEnv-compliant AI agent training environment where agents learn to debug and optimize SQL queries.

## Features

- **3 Difficulty Levels**: Easy (syntax), Medium (logic), Hard (optimization)
- **Dense Reward Function**: Partial credit system (0-1.0 score)
- **OpenEnv Compatible**: Standard REST API endpoints
- **SQLite Backend**: In-memory database per episode

## Quick Start

### Local Testing
```bash
# Start server
uvicorn main:app --host 0.0.0.0 --port 7860

# Test health
curl http://localhost:7860/health

# Reset environment
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{"task_id": "task_easy"}'
```

### API Endpoints

- `GET /` - Health check + list tasks
- `POST /reset` - Start new episode
- `POST /step` - Submit SQL query
- `GET /state` - Get current environment state
- `GET /tasks` - List all tasks

## Tasks

| Task ID | Difficulty | Goal |
|---------|-----------|------|
| task_easy | Easy | Fix syntax errors (SELEC, FORM, WHERE) |
| task_medium | Medium | Fix logic errors (wrong results) |
| task_hard | Hard | Optimize correlated subquery → JOIN |

## Baseline Performance

| Task | Score | Status |
|------|-------|--------|
| task_easy | 1.00 | ✅ Solved |
| task_medium | 1.00 | ✅ Solved |
| task_hard | 0.75 | ⚠️ Partial |
| **Average** | **0.92** | |

## Author

Created for AI agent training and development.
