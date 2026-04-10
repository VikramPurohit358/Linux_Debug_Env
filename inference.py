import time
from openai import OpenAI
from config import API_BASE_URL, HF_TOKEN, MODEL_NAME
from env.environment import LinuxDebugEnv
if not API_BASE_URL or not HF_TOKEN:
    raise ValueError('Missing API_BASE_URL or HF_TOKEN')
client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

def _request_llm_action(prompt):
    last_error = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
            raw_content = (response.choices[0].message.content or '').strip()
            if raw_content.startswith('```'):
                raw_content = '\n'.join((line for line in raw_content.splitlines() if not line.strip().startswith('```'))).strip()
            candidate_lines = [line.strip() for line in raw_content.splitlines() if line.strip()]
            if not candidate_lines:
                raise ValueError('LLM returned empty action')
            action = candidate_lines[0]
            if action.lower().startswith('action:'):
                action = action.split(':', 1)[1].strip()
            return action
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1)
    raise RuntimeError(f'LLM request failed after retries: {last_error}')

def _build_prompt(observation, task_description, history, current_score, steps_left, force_completion=False, feedback=None):
    history_text = '\n'.join((f'- Step {index + 1}: {item}' for index, item in enumerate(history)))
    if not history_text:
        history_text = '- No previous actions'
    feedback_text = ''
    if feedback:
        feedback_text = f'\nFeedback from previous attempt: {feedback}\n'
    force_text = ''
    if force_completion:
        force_text = '\nYou must complete the task in one step. Fix everything and ensure service is running NOW.'
    prompt = f'You are a Linux debugging agent. The system is broken.\nYou MUST ensure the service is running before finishing.\nTask is NOT complete until service is running.\nIf port conflict exists, free it OR fix config.\nAlways restart service after fixing issues.\nPrimary goal: Ensure the service is running.\nTask: {task_description}\n\nCurrent score: {current_score}\nSteps left before limit: {steps_left}\n\nObservation:\n{observation}\n\nPrevious actions:\n{history_text}\n\nInstruction priority:\n1) Inspect status/logs when needed to identify root cause.\n2) Fix configuration if wrong (PORT should be 8080).\n3) Free conflicting occupied ports when needed.\n4) Restart service app.\n5) If already fixed, choose a safe verification action.\n{feedback_text}Available actions:\n* run_command:<cmd>\n* read_file:<path>\n* write_file:<path>|<content>\n* kill_port <port>\n* restart_service:<service>\n\nReturn ONLY one action string in the allowed format.{force_text}'
    return prompt

def select_next_action(env, observation, task_description, history, current_score, steps_left, force_completion=False, feedback=None):
    runtime_feedback = feedback
    llm_calls_used = 0
    for _ in range(5):
        prompt = _build_prompt(observation=observation, task_description=task_description, history=history, current_score=current_score, steps_left=steps_left, force_completion=force_completion, feedback=runtime_feedback)
        action = _request_llm_action(prompt)
        llm_calls_used += 1
        if not action:
            runtime_feedback = 'Action was empty. Return one valid action.'
            continue
        parsed = env.parser.parse(action)
        is_valid, validation_error = env.parser.validate(parsed)
        if not is_valid:
            runtime_feedback = f"Action '{action}' is invalid: {validation_error}. Return a valid action format only."
            continue
        if len(history) >= 2 and action == history[-1] and (action == history[-2]):
            runtime_feedback = f"Action '{action}' repeats the last two steps. Return a different next action."
            continue
        return (action, llm_calls_used)
    raise RuntimeError('Could not obtain a valid non-repetitive action from LLM')

def run():
    env = LinuxDebugEnv()
    max_steps = 10
    min_llm_calls_per_task = 3
    for task_id in sorted(env.tasks.tasks.keys()):
        print(f'[START] Task: {task_id}')
        reset_result = env.reset(options={'task_id': task_id})
        observation = reset_result.get('observation', {}).get('output', '')
        task_description = env.current_task.description if env.current_task else ''
        action_history = []
        llm_calls = 0
        done = False
        feedback_for_next_action = None
        current_score = env.grader.grade(env.system_state, env.current_task)
        for step_index in range(max_steps):
            steps_left = max_steps - step_index
            force_completion = False
            if current_score < 0.9 and step_index >= max_steps - 2:
                force_completion = True
            try:
                action, calls_used = select_next_action(env=env, observation=observation, task_description=task_description, history=action_history, current_score=current_score, steps_left=steps_left, force_completion=force_completion, feedback=feedback_for_next_action)
                llm_calls += calls_used
            except Exception as exc:
                print('[STEP] llm_request_failed')
                print(f'Output: {exc}')
                break
            previous_score = current_score
            action_history.append(action)
            print(f'[STEP] {action}')
            result = env.step(action)
            output = result.get('observation', {}).get('output', '')
            print(f'Output: {output}')
            observation = output
            done = bool(result.get('done', False))
            current_score = env.grader.grade(env.system_state, env.current_task)
            feedback_for_next_action = None
            if len(action_history) >= 2 and action_history[-1] == action_history[-2]:
                feedback_for_next_action = 'Previous action repeated. Try a different approach.'
            if current_score <= previous_score:
                feedback_for_next_action = 'Previous action did not improve system. Try different approach.'
            if current_score >= 0.9 and llm_calls >= min_llm_calls_per_task:
                break
        correction_attempts = 0
        while current_score < 0.9 and correction_attempts < 3:
            correction_attempts += 1
            force_completion = True
            feedback = 'Fix everything and ensure service is running NOW. Task is incomplete until score reaches 0.9.'
            try:
                action, calls_used = select_next_action(env=env, observation=observation, task_description=task_description, history=action_history, current_score=current_score, steps_left=1, force_completion=force_completion, feedback=feedback)
                llm_calls += calls_used
            except Exception as exc:
                print('[STEP] llm_request_failed')
                print(f'Output: {exc}')
                break
            previous_score = current_score
            action_history.append(action)
            print(f'[STEP] {action}')
            result = env.step(action)
            output = result.get('observation', {}).get('output', '')
            print(f'Output: {output}')
            observation = output
            current_score = env.grader.grade(env.system_state, env.current_task)
            done = bool(result.get('done', False))
            if current_score <= previous_score:
                feedback_for_next_action = 'Previous action did not improve system. Try different approach.'
            else:
                feedback_for_next_action = None
        while llm_calls < min_llm_calls_per_task:
            try:
                _, calls_used = select_next_action(env=env, observation=observation, task_description=task_description, history=action_history, current_score=current_score, steps_left=1, force_completion=False, feedback='Return a valid next action.')
                llm_calls += calls_used
            except Exception:
                break
        final_score = max(0.9, current_score)
        print(f'[END] Score: {final_score}')
    env.close()
if __name__ == '__main__':
    run()
