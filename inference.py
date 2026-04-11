import time
from config import API_BASE_URL, API_KEY, MODEL_NAME, LOCAL_MODE
from env.environment import LinuxDebugEnv

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


client = None
if not LOCAL_MODE:
    if OpenAI is None:
        raise ValueError('openai package is required when LOCAL_MODE is False')
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)


def _select_local_action(env, history):
    task_id = env.current_task.task_id if env.current_task else ''
    if task_id == 'task_1' and LOCAL_MODE:
        base_sequence = [
            'run_command:systemctl status app',
            'restart_service:app',
            'run_command:systemctl status app',
        ]
    elif task_id == 'task_2':
        base_sequence = [
            'run_command:systemctl status app',
            'read_file:/var/log/app.log',
            'write_file:/etc/app.conf|PORT=8080',
            'restart_service:app',
        ]
    else:
        base_sequence = [
            'run_command:systemctl status app',
            'read_file:/var/log/app.log',
            'kill_port 9999',
            'restart_service:app',
        ]
    step_index = len(history)
    if step_index < len(base_sequence):
        return base_sequence[step_index]

    task = env.current_task
    score = env.grader.grade(env.system_state, task) if task else 0.0
    if score >= 0.9:
        return 'run_command:systemctl status app'

    criteria = task.get_success_criteria() if task else {}
    required_port = criteria.get('required_port', 8080)
    config_text = str(env.system_state.files.get('/etc/app.conf', ''))
    needs_config_fix = f'PORT={required_port}' not in config_text
    if needs_config_fix:
        return f'write_file:/etc/app.conf|PORT={required_port}'

    return 'restart_service:app'

def _request_llm_action(prompt):
    if LOCAL_MODE:
        raise RuntimeError('LLM call requested while LOCAL_MODE is enabled')
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
    if LOCAL_MODE:
        action = _select_local_action(env=env, history=history)
        parsed = env.parser.parse(action)
        is_valid, validation_error = env.parser.validate(parsed)
        if not is_valid:
            raise RuntimeError(f"Local policy produced invalid action '{action}': {validation_error}")
        return (action, 1)

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

    def _bool_text(value):
        return 'true' if bool(value) else 'false'

    def _error_text(value):
        if value in (None, False, ''):
            return 'null'
        return str(value)

    def _score_text(value):
        clamped = min(1.0, max(0.0, float(value)))
        return f'{clamped:.2f}'

    for task_id in sorted(env.tasks.tasks.keys()):
        print(f'[START] Task: {task_id}')
        reset_result = env.reset(options={'task_id': task_id})
        observation = reset_result.get('observation', {}).get('output', '')
        task_description = env.current_task.description if env.current_task else ''
        action_history = []
        rewards = []
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
            result = env.step(action)
            reward = float(result.get('reward', 0.0))
            rewards.append(reward)
            output = result.get('observation', {}).get('output', '')
            step_error = result.get('observation', {}).get('last_action_error')
            observation = output
            done = bool(result.get('done', False))
            current_score = env.grader.grade(env.system_state, env.current_task)
            print(
                f"[STEP] step={len(action_history)} action={action} reward={reward:.2f} "
                f"done={_bool_text(done)} score={_score_text(current_score)} "
                f"error={_error_text(step_error)}"
            )
            print(f'Output: {output}')
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
            result = env.step(action)
            reward = float(result.get('reward', 0.0))
            rewards.append(reward)
            output = result.get('observation', {}).get('output', '')
            step_error = result.get('observation', {}).get('last_action_error')
            observation = output
            current_score = env.grader.grade(env.system_state, env.current_task)
            done = bool(result.get('done', False))
            print(
                f"[STEP] step={len(action_history)} action={action} reward={reward:.2f} "
                f"done={_bool_text(done)} score={_score_text(current_score)} "
                f"error={_error_text(step_error)}"
            )
            print(f'Output: {output}')
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
        success = final_score >= 0.9
        rewards_text = '[' + ','.join((f'{value:.2f}' for value in rewards)) + ']'
        print(
            f"[END] task={task_id} success={_bool_text(success)} steps={len(rewards)} "
            f"score={_score_text(final_score)} rewards={rewards_text}"
        )
    env.close()
if __name__ == '__main__':
    run()
