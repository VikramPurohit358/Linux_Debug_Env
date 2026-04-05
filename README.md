---
title: Linux Debugging OpenEnv
emoji: 🐧
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Linux Debugging Environment

An OpenEnv-compatible environment where agents debug realistic Linux service failures through observable system state and actionable remediation steps.

## Why this matters
Real production incidents rarely fail cleanly.


- A service is down
- Logs hint at the root cause
- Config is wrong
- A port is already in use

Fixing it requires **inspection → reasoning → action → verification**.

This environment models that exact workflow — making it suitable for evaluating agents on **practical debugging tasks**, not synthetic benchmarks.

## What this environment simulates

- Reading and interpreting logs (`/var/log/app.log`)
- Checking service status (`systemctl status app`)
- Fixing broken configuration (`/etc/app.conf`)
- Resolving port conflicts (`kill_port <port>`)
- Restarting services and validating recovery

Each action mutates system state deterministically.

## Task Design

- **task_1 (easy):** service is stopped, restart correctly.
- **task_2 (medium):** config points to an occupied port, fix config before restart.
- **task_3 (hard):** diagnose via logs and choose valid remediation before restart.

Complexity increases from direct recovery to diagnosis-driven recovery.

## Action Space

run_command:<command>
read_file:<path>
write_file:<path>|<content>
kill_port <port>
restart_service:<service>

Actions are structured, deterministic, and directly tied to system state changes.

## Reward Design

- Reward is progress-based, not binary:

```text
reward = new_progress - previous_progress
```

- Score levels are deterministic:
  - `0.0` → no progress
  - `0.5` → partial progress
  - `1.0` → task solved

This encourages agents to value **correct intermediate steps**, not just final success.

## Example Workflow

A typical solution path:

1. Check service status
2. Read logs
3. Identify root cause
4. Apply fix (update config or free port)
5. Restart service
6. Verify success (`score = 1.0`)

## API Endpoints

- `GET /` → health + endpoint overview
- `POST /reset` → reset environment
- `POST /step` → execute one action (`{ "action": "..." }`)
- `GET /tasks` → list tasks
- `GET /grader` → current score
- `GET /baseline` → deterministic reference solution

## How to Run

### Local

```bash
cd linux_env
uvicorn api.server:app --host 0.0.0.0 --port 7860
```

### Docker

```bash
cd linux_env
docker build -t linux-debug-env .
docker run --rm -p 7860:7860 linux-debug-env
```

### Quick test

```bash
curl -X POST http://localhost:7860/reset
```

## Hugging Face Deployment

- Runs as a **Docker Space**
- FastAPI served via `uvicorn api.server:app`
- Uses port `7860`

Optional environment variables:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

## Example Inference Output

```text
[START] Task: task_1
[STEP] run_command:systemctl status app
Output: ● app.service - Mock Service
[STEP] run_command:cat /var/log/app.log
Output: ERROR: Port 9999 already in use
[STEP] run_command:kill_port 9999
Output: Freed port 9999
[STEP] restart_service:app
Output: Restarted app. Service is running.
[END] Score: 1.0
```