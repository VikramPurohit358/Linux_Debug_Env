class Task:

    def __init__(self, task_id, description):
        self.task_id = task_id
        self.description = description

    def setup(self, state):
        raise NotImplementedError

    def get_success_criteria(self):
        raise NotImplementedError

class Task1Easy(Task):

    def __init__(self):
        super().__init__(task_id='task_1', description='Service app is stopped. Restart the service.')

    def setup(self, state):
        state.update_file('/etc/app.conf', 'PORT=8080')
        state.update_file('/var/log/app.log', 'ERROR: Port 9999 already in use')
        state.update_service('app', 'stopped')
        state.update_port(8080, 'free')
        state.update_port(9999, 'occupied')
        state.update_env('logs_read', '0')

    def get_success_criteria(self):
        return {'service': 'running', 'required_port': 8080, 'requires_logs_read': False, 'allow_free_port_path': False}

class Task2Medium(Task):

    def __init__(self):
        super().__init__(task_id='task_2', description='Config is PORT=9999 and port 9999 is occupied. Set PORT=8080 and restart service.')

    def setup(self, state):
        state.update_file('/etc/app.conf', 'PORT=9999')
        state.update_file('/var/log/app.log', 'ERROR: Port 9999 already in use')
        state.update_service('app', 'stopped')
        state.update_port(8080, 'free')
        state.update_port(9999, 'occupied')
        state.update_env('logs_read', '0')

    def get_success_criteria(self):
        return {'service': 'running', 'required_port': 8080, 'requires_logs_read': False, 'allow_free_port_path': False}

class Task3Hard(Task):

    def __init__(self):
        super().__init__(task_id='task_3', description='Port is occupied and config is wrong. Read logs, identify issue, fix config OR free the port, then restart service.')

    def setup(self, state):
        state.update_file('/etc/app.conf', 'PORT=9999')
        state.update_file('/var/log/app.log', 'ERROR: Port 9999 already in use. Check /etc/app.conf or free the port')
        state.update_service('app', 'stopped')
        state.update_port(8080, 'free')
        state.update_port(9999, 'occupied')
        state.update_env('logs_read', '0')

    def get_success_criteria(self):
        return {'service': 'running', 'required_port': 8080, 'requires_logs_read': True, 'allow_free_port_path': True, 'conflict_port': 9999}

class TaskLibrary:

    def __init__(self):
        self.tasks = {'task_1': Task1Easy(), 'task_2': Task2Medium(), 'task_3': Task3Hard()}

    def get_task(self, task_id):
        return self.tasks.get(task_id, self.tasks['task_1'])
