"""Deterministic inference runner for LinuxDebugEnv."""

import os

from openai import OpenAI

from env.environment import LinuxDebugEnv


API_BASE_URL = os.getenv("API_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
HF_TOKEN = os.getenv("HF_TOKEN")

client = OpenAI(base_url=API_BASE_URL, api_key="dummy")


def run():
    """Run deterministic baseline for all tasks with strict print format."""
    env = LinuxDebugEnv()
    task_actions = {
        "task_1": [
            "run_command:systemctl status app",
            "run_command:cat /var/log/app.log",
            "run_command:kill_port 9999",
            "restart_service:app",
        ],
        "task_2": [
            "run_command:systemctl status app",
            "run_command:cat /var/log/app.log",
            "write_file: /etc/app.conf|PORT=8080",
            "restart_service:app",
        ],
        "task_3": [
            "run_command:systemctl status app",
            "run_command:cat /var/log/app.log",
            "run_command:kill_port 9999",
            "restart_service:app",
        ],
    }

    for task_id in sorted(env.tasks.tasks.keys()):
        print(f"[START] Task: {task_id}")
        env.reset(options={"task_id": task_id})

        for action in task_actions[task_id]:
            print(f"[STEP] {action}")
            result = env.step(action)
            output = result.get("observation", {}).get("output", "")
            print(f"Output: {output}")

        score = env.grader.grade(env.state, env.current_task)
        print(f"[END] Score: {score}")

    env.close()


if __name__ == "__main__":
    run()
