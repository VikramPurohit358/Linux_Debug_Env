"""Main environment interface - OpenEnv compatible."""

from .state import SystemState
from .actions import ActionParser, ActionExecutor
from .tasks import TaskLibrary
from .grader import Grader


class LinuxDebugEnv:
    """OpenEnv-compatible Linux debugging environment."""
    
    def __init__(self, config=None):
        """Initialize environment."""
        self.config = config or {}
        self.state = SystemState()
        self.parser = ActionParser()
        self.executor = ActionExecutor(state=self.state)
        self.tasks = TaskLibrary()
        self.grader = Grader()
        self.current_task = None
        self.step_count = 0
    
    def reset(self, seed=None, options=None):
        """Reset environment and start new episode."""
        options = options or {}
        task_id = options.get('task_id', 'task_1')

        self.state.reset()
        self.executor.set_state(self.state)
        self.current_task = self.tasks.get_task(task_id)
        self.current_task.setup(self.state)
        self.step_count = 0

        return {
            "observation": {
                "output": f"Environment reset. Task: {self.current_task.description}",
                "last_action_error": False
            },
            "info": {}
        }
    
    def step(self, action):
        """Execute action and return OpenEnv-style step result dict."""
        previous_progress = 0.0
        if self.current_task:
            previous_progress = self.grader.grade(self.state, self.current_task)

        parsed = self.parser.parse(action)
        is_valid, validation_error = self.parser.validate(parsed)

        execution_result = {
            "output": "",
            "error": validation_error or "",
        }

        if is_valid:
            execution_result = self.executor.execute(parsed)

        output = str(execution_result.get("output", ""))
        has_error = bool(execution_result.get("error"))

        new_progress = previous_progress
        if self.current_task:
            new_progress = self.grader.grade(self.state, self.current_task)

        if new_progress == 1.0:
            reward = 1.0
            done = True
        else:
            reward = float(new_progress - previous_progress)
            done = False

        self.step_count += 1

        return {
            "observation": {
                "output": output,
                "last_action_error": has_error,
            },
            "reward": reward,
            "done": done,
            "info": {
                "previous_progress": previous_progress,
                "new_progress": new_progress,
            },
        }

    def state(self):
        return self.state.to_dict()
    
    def close(self):
        """Close environment."""
        pass
