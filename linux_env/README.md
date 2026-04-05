# Linux Debugging Environment

Linux debugging environment for AI agents with deterministic tasks, scoring, and a FastAPI interface.

## Run locally

```bash
cd linux_env
python inference.py
```

Run API server:

```bash
cd linux_env
uvicorn api.server:app --host 0.0.0.0 --port 7860
```

## Run with Docker

```bash
cd linux_env
docker build -t linux-debug-env .
docker run --rm -p 7860:7860 linux-debug-env
```

## API endpoints

- `POST /reset` → reset environment
- `POST /step` with `{ "action": "..." }` → apply one action
- `GET /tasks` → list task IDs and descriptions
- `GET /grader` → current score
- `GET /baseline` → run status → logs → kill_port → restart baseline

## Tasks

- `task_1` (easy): service stopped, restart service
- `task_2` (medium): config points to occupied port, fix config then restart
- `task_3` (hard): read logs, resolve conflict (free port or fix config), restart

## Example inference output

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

