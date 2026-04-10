from fastapi import FastAPI
from pydantic import BaseModel
try:
    from config import API_BASE_URL, HF_TOKEN, MODEL_NAME
    from env.environment import LinuxDebugEnv
except ImportError:
    from ..config import API_BASE_URL, HF_TOKEN, MODEL_NAME
    from ..env.environment import LinuxDebugEnv
app = FastAPI(title='Linux Debugging Environment API')
env = LinuxDebugEnv()
app.state.api_base_url = API_BASE_URL
app.state.model_name = MODEL_NAME
app.state.hf_token = HF_TOKEN

@app.get('/')
def root():
    return {'message': 'Linux Debug Environment API is running', 'available_endpoints': ['/reset', '/step', '/tasks', '/grader', '/baseline']}

class StepRequest(BaseModel):
    action: str

@app.post('/reset')
def reset_env():
    return env.reset()

@app.post('/step')
def step_env(payload: StepRequest):
    return env.step(payload.action)

@app.get('/tasks')
def list_tasks():
    return [{'task_id': task.task_id, 'description': task.description} for task in env.tasks.tasks.values()]

@app.get('/grader')
def grader_score():
    if env.current_task is None:
        return {'score': 0.0}
    return {'score': env.grader.grade(env.system_state, env.current_task)}

@app.get('/baseline')
def run_baseline():
    env.reset(options={'task_id': 'task_3'})
    actions = ['run_command:systemctl status app', 'run_command:cat /var/log/app.log', 'run_command:kill_port 9999', 'restart_service:app']
    for action in actions:
        env.step(action)
    final_score = env.grader.grade(env.system_state, env.current_task)
    return {'score': final_score}
