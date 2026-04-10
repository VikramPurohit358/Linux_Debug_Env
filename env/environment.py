from .state import SystemState
from .actions import ActionParser, ActionExecutor
from .tasks import TaskLibrary
from .grader import Grader

class LinuxDebugEnv:

    def __init__(self, config=None):
        self.config = config or {}
        self.system_state = SystemState()
        self.parser = ActionParser()
        self.executor = ActionExecutor(state=self.system_state)
        self.tasks = TaskLibrary()
        self.grader = Grader()
        self.current_task = None
        self.step_count = 0

    def reset(self, seed=None, options=None):
        options = options or {}
        task_id = options.get('task_id', 'task_1')
        self.system_state.reset()
        self.executor.set_state(self.system_state)
        self.current_task = self.tasks.get_task(task_id)
        self.current_task.setup(self.system_state)
        self.step_count = 0
        return {'observation': {'output': f'Environment reset. Task: {self.current_task.description}', 'last_action_error': False}, 'info': {}}

    def step(self, action):
        previous_progress = 0.1
        if self.current_task:
            previous_progress = self.grader.grade(self.system_state, self.current_task)
        parsed = self.parser.parse(action)
        is_valid, validation_error = self.parser.validate(parsed)
        execution_result = {'output': '', 'error': validation_error or ''}
        if is_valid:
            execution_result = self.executor.execute(parsed)
        output = str(execution_result.get('output', ''))
        has_error = bool(execution_result.get('error'))
        new_progress = previous_progress
        if self.current_task:
            new_progress = self.grader.grade(self.system_state, self.current_task)
        reward = float(new_progress - previous_progress)
        done = bool(self.current_task and self.grader.evaluate(self.system_state, self.current_task))
        self.step_count += 1
        return {'observation': {'output': output, 'last_action_error': has_error}, 'reward': reward, 'done': done, 'info': {'previous_progress': previous_progress, 'new_progress': new_progress}}

    def state(self):
        return self.system_state.to_dict()

    def close(self):
        pass
