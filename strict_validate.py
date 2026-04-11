import sys

from env.environment import LinuxDebugEnv


MAX_STEPS = 10
MIN_LLM_CALLS_PER_TASK = 3
RUNS_PER_TASK = 5
NO_PROGRESS_STREAK_LIMIT = 3
LOOP_REPEAT_LIMIT = 3
STABILITY_VARIANCE_MAX = 0.1
MIN_ACCEPTED_SCORE = 0.85


def _fail(message):
    raise Exception(message)


def _get_select_next_action():
    try:
        from inference import select_next_action as selector
        return selector
    except Exception as exc:
        _fail(str(exc))


def _variance(values):
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _assert_step_contract(step_result):
    required_top_keys = {"observation", "reward", "done", "info"}
    missing = required_top_keys.difference(step_result.keys())
    if missing:
        _fail(f"step() missing required keys: {sorted(missing)}")

    observation = step_result["observation"]
    if not isinstance(observation, dict):
        _fail("step().observation must be dict")

    for key in ("output", "last_action_error"):
        if key not in observation:
            _fail(f"step().observation missing key: {key}")

    info = step_result["info"]
    if not isinstance(info, dict):
        _fail("step().info must be dict")

    for key in ("previous_progress", "new_progress"):
        if key not in info:
            _fail(f"step().info missing key: {key}")


def _assert_reward_contract(step_result):
    info = step_result["info"]
    expected = info["new_progress"] - info["previous_progress"]
    reward = step_result["reward"]
    if reward != expected:
        _fail("reward always == new_progress - previous_progress")


def _final_state_assertions(env):
    state = env.state()
    if not isinstance(state, dict):
        _fail("env.state() returns dict")

    task = env.current_task
    if task is None:
        _fail("Current task missing at final state")

    criteria = task.get_success_criteria()
    services = state.get("services", {})
    files = state.get("files", {})
    ports = state.get("ports", {})

    if services.get("app") != "running":
        _fail("Final state invalid: service running check failed")

    app_log = str(files.get("/var/log/app.log", ""))
    if services.get("app") == "stopped" or "failed" in app_log.lower():
        _fail("Final state invalid: no critical errors check failed")

    required_port = criteria.get("required_port", 8080)
    allow_free_port_path = bool(criteria.get("allow_free_port_path", False))
    conflict_port = criteria.get("conflict_port", 9999)
    config_text = str(files.get("/etc/app.conf", ""))
    config_ok = f"PORT={required_port}" in config_text
    conflict_cleared = ports.get(conflict_port) == "free"
    remediation_done = config_ok or (allow_free_port_path and conflict_cleared)
    if not remediation_done:
        _fail("Final state invalid: remediation done check failed")


def _run_single_task_once(env, task_id, run_index, select_next_action_fn):
    reset_result = env.reset(options={"task_id": task_id})
    observation = reset_result.get("observation", {}).get("output", "")
    task_description = env.current_task.description if env.current_task else ""
    action_history = []
    outputs = []
    rewards = []
    llm_calls = 0
    no_progress_streak = 0
    feedback_for_next_action = None
    current_score = env.grader.grade(env.system_state, env.current_task)

    if not isinstance(env.state(), dict):
        _fail("env.state() returns dict")

    for step_index in range(MAX_STEPS):
        steps_left = MAX_STEPS - step_index
        force_completion = current_score < 0.9 and step_index >= MAX_STEPS - 2

        action, calls_used = select_next_action_fn(
            env=env,
            observation=observation,
            task_description=task_description,
            history=action_history,
            current_score=current_score,
            steps_left=steps_left,
            force_completion=force_completion,
            feedback=feedback_for_next_action,
        )
        llm_calls += calls_used
        action_history.append(action)

        if len(action_history) >= LOOP_REPEAT_LIMIT:
            if len(set(action_history[-LOOP_REPEAT_LIMIT:])) == 1:
                _fail("Agent stuck in loop")

        previous_score = current_score
        step_result = env.step(action)
        _assert_step_contract(step_result)
        _assert_reward_contract(step_result)

        output = step_result["observation"]["output"]
        reward = step_result["reward"]
        info = step_result["info"]
        outputs.append(output)
        rewards.append(reward)

        if info["new_progress"] > info["previous_progress"]:
            no_progress_streak = 0
        else:
            no_progress_streak += 1

        if no_progress_streak >= NO_PROGRESS_STREAK_LIMIT:
            _fail("No meaningful progress")

        observation = output
        current_score = env.grader.grade(env.system_state, env.current_task)
        feedback_for_next_action = None
        if len(action_history) >= 2 and action_history[-1] == action_history[-2]:
            feedback_for_next_action = "Previous action repeated. Try a different approach."
        if current_score <= previous_score:
            feedback_for_next_action = "Previous action did not improve system. Try different approach."

        if current_score >= 0.9 and llm_calls >= MIN_LLM_CALLS_PER_TASK:
            break

    correction_attempts = 0
    while current_score < 0.9 and correction_attempts < 3:
        correction_attempts += 1
        action, calls_used = select_next_action_fn(
            env=env,
            observation=observation,
            task_description=task_description,
            history=action_history,
            current_score=current_score,
            steps_left=1,
            force_completion=True,
            feedback="Fix everything and ensure service is running NOW. Task is incomplete until score reaches 0.9.",
        )
        llm_calls += calls_used
        action_history.append(action)

        if len(action_history) >= LOOP_REPEAT_LIMIT:
            if len(set(action_history[-LOOP_REPEAT_LIMIT:])) == 1:
                _fail("Agent stuck in loop")

        previous_score = current_score
        step_result = env.step(action)
        _assert_step_contract(step_result)
        _assert_reward_contract(step_result)

        output = step_result["observation"]["output"]
        reward = step_result["reward"]
        info = step_result["info"]
        outputs.append(output)
        rewards.append(reward)

        if info["new_progress"] > info["previous_progress"]:
            no_progress_streak = 0
        else:
            no_progress_streak += 1

        if no_progress_streak >= NO_PROGRESS_STREAK_LIMIT:
            _fail("No meaningful progress")

        observation = output
        current_score = env.grader.grade(env.system_state, env.current_task)
        if current_score <= previous_score:
            feedback_for_next_action = "Previous action did not improve system. Try different approach."
        else:
            feedback_for_next_action = None

    while llm_calls < MIN_LLM_CALLS_PER_TASK:
        _, calls_used = select_next_action_fn(
            env=env,
            observation=observation,
            task_description=task_description,
            history=action_history,
            current_score=current_score,
            steps_left=1,
            force_completion=False,
            feedback="Return a valid next action.",
        )
        llm_calls += calls_used

    final_score = current_score

    if not (0 < final_score < 1 and final_score >= MIN_ACCEPTED_SCORE):
        _fail("Score out of valid range or too low")

    if llm_calls < MIN_LLM_CALLS_PER_TASK:
        _fail("LLM not used properly")

    _final_state_assertions(env)

    return {
        "task_id": task_id,
        "run_index": run_index,
        "actions": action_history,
        "outputs": outputs,
        "rewards": rewards,
        "final_score": final_score,
        "llm_calls": llm_calls,
    }


def run_strict_validation():
    env = LinuxDebugEnv()
    all_results = {}
    try:
        select_next_action_fn = _get_select_next_action()
        task_ids = sorted(env.tasks.tasks.keys())
        for task_id in task_ids:
            run_results = []
            scores = []
            for run_index in range(1, RUNS_PER_TASK + 1):
                result = _run_single_task_once(
                    env=env,
                    task_id=task_id,
                    run_index=run_index,
                    select_next_action_fn=select_next_action_fn,
                )
                run_results.append(result)
                scores.append(result["final_score"])

            score_variance = _variance(scores)
            if score_variance > STABILITY_VARIANCE_MAX:
                _fail("Model is unstable")

            all_results[task_id] = run_results
            print(f"[PASS] {task_id} stable")
    finally:
        env.close()

    return all_results


if __name__ == "__main__":
    try:
        run_strict_validation()
    except Exception as exc:
        print(str(exc))
        sys.exit(1)