"""FastAPI server for the Linux debugging environment."""

from fastapi import FastAPI
from pydantic import BaseModel

try:
    from config import API_BASE_URL, HF_TOKEN, MODEL_NAME
	from env.environment import LinuxDebugEnv
except ImportError:  # pragma: no cover
    from ..config import API_BASE_URL, HF_TOKEN, MODEL_NAME
	from ..env.environment import LinuxDebugEnv


app = FastAPI(title="Linux Debugging Environment API")
env = LinuxDebugEnv()
app.state.api_base_url = API_BASE_URL
app.state.model_name = MODEL_NAME
app.state.hf_token = HF_TOKEN


@app.get("/")
def root():
    """Health and endpoint discovery route."""
    return {
        "message": "Linux Debug Environment API is running",
        "available_endpoints": [
            "/reset",
            "/step",
            "/tasks",
            "/grader",
            "/baseline",
        ],
    }


class StepRequest(BaseModel):
    """Request model for step endpoint."""

    action: str


@app.post("/reset")
def reset_env():
    """Reset the environment and return reset result."""
    return env.reset()


@app.post("/step")
def step_env(payload: StepRequest):
    """Run one action in the environment."""
    return env.step(payload.action)


@app.get("/tasks")
def list_tasks():
    """Return available tasks with IDs and descriptions."""
    return [
        {"task_id": task.task_id, "description": task.description}
        for task in env.tasks.tasks.values()
    ]


@app.get("/grader")
def grader_score():
    """Return current score for the active task."""
    if env.current_task is None:
        return {"score": 0.0}
    return {"score": env.grader.grade(env.system_state, env.current_task)}


@app.get("/baseline")
def run_baseline():
    """Run status -> logs -> kill_port -> restart and return final score."""
    env.reset(options={"task_id": "task_3"})

    actions = [
        "run_command:systemctl status app",
        "run_command:cat /var/log/app.log",
        "run_command:kill_port 9999",
        "restart_service:app",
    ]

    for action in actions:
        env.step(action)

    final_score = env.grader.grade(env.system_state, env.current_task)
    return {"score": final_score}
