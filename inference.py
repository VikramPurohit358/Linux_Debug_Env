import time

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

    last_error = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_content = (response.choices[0].message.content or "").strip()
            if raw_content.startswith("```"):
                raw_content = "\n".join(
                    line
                    for line in raw_content.splitlines()
                    if not line.strip().startswith("```")
                ).strip()

            candidate_lines = [line.strip() for line in raw_content.splitlines() if line.strip()]
            if not candidate_lines:
                raise ValueError("LLM returned empty action")

            action = candidate_lines[0]
            if action.lower().startswith("action:"):
                action = action.split(":", 1)[1].strip()
            return action
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1)

    raise RuntimeError(f"LLM request failed after retries: {last_error}")


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
            try:
                action = select_next_action(
                    observation=observation,
                    task_description=task_description,
                    history=action_history,
                )
            except Exception as exc:
                print("[STEP] llm_request_failed")
                print(f"Output: {exc}")
                break

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
