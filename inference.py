"""LLM-driven inference runner for LinuxDebugEnv."""

from openai import OpenAI

from config import API_BASE_URL, HF_TOKEN, MODEL_NAME
from env.environment import LinuxDebugEnv

if not API_BASE_URL or not HF_TOKEN:
    raise ValueError("Missing API_BASE_URL or HF_TOKEN")

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN,
)


def select_next_action(observation, task_description, history):
    history_text = "\n".join(
        f"- Step {index + 1}: {item}" for index, item in enumerate(history)
    )
    if not history_text:
        history_text = "- No previous actions"

    prompt = (
        "You are a Linux debugging agent. The system is broken.\n"
        "Goal: fix the system so the service is healthy.\n"
        f"Task: {task_description}\n\n"
        "Observation:\n"
        f"{observation}\n\n"
        "Previous actions:\n"
        f"{history_text}\n\n"
        "Available actions:\n"
        "* run_command:<cmd>\n"
        "* read_file:<path>\n"
        "* write_file:<path>|<content>\n"
        "* kill_port <port>\n"
        "* restart_service:<service>\n\n"
        "Return ONLY the next best action."
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
    )
    return (response.choices[0].message.content or "").strip().splitlines()[0].strip()


def run():
    env = LinuxDebugEnv()
    max_steps = 10
    min_llm_calls_per_task = 3

    for task_id in sorted(env.tasks.tasks.keys()):
        print(f"[START] Task: {task_id}")
        reset_result = env.reset(options={"task_id": task_id})
        observation = reset_result.get("observation", {}).get("output", "")
        task_description = env.current_task.description if env.current_task else ""
        action_history = []
        llm_calls = 0
        done = False

        for _ in range(max_steps):
            action = select_next_action(
                observation=observation,
                task_description=task_description,
                history=action_history,
            )
            llm_calls += 1
            action_history.append(action)
            print(f"[STEP] {action}")
            result = env.step(action)
            output = result.get("observation", {}).get("output", "")
            print(f"Output: {output}")

            observation = output
            done = bool(result.get("done", False))
            if done and llm_calls >= min_llm_calls_per_task:
                break

        score = env.grader.grade(env.system_state, env.current_task)
        print(f"[END] Score: {score}")

    env.close()


if __name__ == "__main__":
    run()
