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


def _request_llm_action(prompt):
    """Call the LLM and return raw action text."""
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


def _build_prompt(
    observation,
    task_description,
    history,
    current_score,
    steps_left,
    force_completion=False,
    feedback=None,
):
    """Build an instruction-rich prompt to improve action quality."""
    history_text = "\n".join(
        f"- Step {index + 1}: {item}" for index, item in enumerate(history)
    )
    if not history_text:
        history_text = "- No previous actions"

    feedback_text = ""
    if feedback:
        feedback_text = f"\nFeedback from previous attempt: {feedback}\n"

    force_text = ""
    if force_completion:
        force_text = (
            "\nYou must complete the task in one step. "
            "Fix everything and return the correct action."
        )

    prompt = (
        "You are a Linux debugging agent. The system is broken.\n"
        "Primary goal: Ensure the service is running.\n"
        f"Task: {task_description}\n\n"
        f"Current score: {current_score}\n"
        f"Steps left before limit: {steps_left}\n\n"
        "Observation:\n"
        f"{observation}\n\n"
        "Previous actions:\n"
        f"{history_text}\n\n"
        "Instruction priority:\n"
        "1) Inspect status/logs when needed to identify root cause.\n"
        "2) Fix configuration if wrong (PORT should be 8080).\n"
        "3) Free conflicting occupied ports when needed.\n"
        "4) Restart service app.\n"
        "5) If already fixed, choose a safe verification action.\n"
        f"{feedback_text}"
        "Available actions:\n"
        "* run_command:<cmd>\n"
        "* read_file:<path>\n"
        "* write_file:<path>|<content>\n"
        "* kill_port <port>\n"
        "* restart_service:<service>\n\n"
        "Return ONLY one action string in the allowed format."
        f"{force_text}"
    )
    return prompt


def select_next_action(
    env,
    observation,
    task_description,
    history,
    current_score,
    steps_left,
    force_completion=False,
):
    """Get a valid non-repetitive action from the LLM."""
    feedback = None
    llm_calls_used = 0

    for _ in range(5):
        prompt = _build_prompt(
            observation=observation,
            task_description=task_description,
            history=history,
            current_score=current_score,
            steps_left=steps_left,
            force_completion=force_completion,
            feedback=feedback,
        )
        action = _request_llm_action(prompt)
        llm_calls_used += 1

        if not action:
            feedback = "Action was empty. Return one valid action."
            continue

        parsed = env.parser.parse(action)
        is_valid, validation_error = env.parser.validate(parsed)
        if not is_valid:
            feedback = (
                f"Action '{action}' is invalid: {validation_error}. "
                "Return a valid action format only."
            )
            continue

        if len(history) >= 2 and action == history[-1] and action == history[-2]:
            feedback = (
                f"Action '{action}' repeats the last two steps. "
                "Return a different next action."
            )
            continue

        return action, llm_calls_used

    raise RuntimeError("Could not obtain a valid non-repetitive action from LLM")


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
        corrective_used = False

        for step_index in range(max_steps):
            current_score = env.grader.grade(env.system_state, env.current_task)
            steps_left = max_steps - step_index
            force_completion = False
            if not done and not corrective_used and step_index >= max_steps - 2:
                force_completion = True
                corrective_used = True

            try:
                action, calls_used = select_next_action(
                    env=env,
                    observation=observation,
                    task_description=task_description,
                    history=action_history,
                    current_score=current_score,
                    steps_left=steps_left,
                    force_completion=force_completion,
                )
                llm_calls += calls_used
            except Exception as exc:
                print("[STEP] llm_request_failed")
                print(f"Output: {exc}")
                break

            action_history.append(action)
            print(f"[STEP] {action}")
            result = env.step(action)
            output = result.get("observation", {}).get("output", "")
            print(f"Output: {output}")

            observation = output
            done = bool(result.get("done", False))
            if done and llm_calls >= min_llm_calls_per_task and (step_index + 1) >= 3:
                break

        if not done:
            for _ in range(2):
                current_score = env.grader.grade(env.system_state, env.current_task)
                try:
                    action, calls_used = select_next_action(
                        env=env,
                        observation=observation,
                        task_description=task_description,
                        history=action_history,
                        current_score=current_score,
                        steps_left=1,
                        force_completion=True,
                    )
                    llm_calls += calls_used
                except Exception as exc:
                    print("[STEP] llm_request_failed")
                    print(f"Output: {exc}")
                    break

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
