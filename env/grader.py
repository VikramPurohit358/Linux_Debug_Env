class Grader:
    CONFIG_PATH = '/etc/app.conf'
    MIN_SCORE = 0.1
    PARTIAL_SCORE = 0.5
    SUCCESS_SCORE = 0.9

    def grade(self, state, task):
        criteria = task.get_success_criteria()
        service_running = state.services.get('app') == criteria.get('service', 'running')
        logs_ok = self._logs_read_ok(state, criteria)
        required_port = criteria.get('required_port', 8080)
        config_matches_required = self._config_port(state) == required_port
        allow_free_port_path = bool(criteria.get('allow_free_port_path', False))
        conflict_port = criteria.get('conflict_port', 9999)
        conflict_cleared = state.ports.get(conflict_port, 'occupied') == 'free'
        remediation_ok = config_matches_required or (allow_free_port_path and conflict_cleared)
        if service_running and logs_ok and remediation_ok:
            return self._clamp_score(self.SUCCESS_SCORE)
        if remediation_ok and (not service_running):
            return self._clamp_score(self.PARTIAL_SCORE)
        if criteria.get('requires_logs_read', False) and logs_ok and remediation_ok:
            return self._clamp_score(self.PARTIAL_SCORE)
        return self._clamp_score(self.MIN_SCORE)

    def evaluate(self, state, task):
        return self.grade(state, task) >= self.SUCCESS_SCORE

    def _config_port(self, state):
        content = state.files.get(self.CONFIG_PATH, '')
        for line in str(content).splitlines():
            line = line.strip()
            if line.startswith('PORT='):
                value = line.split('=', 1)[1].strip()
                if value.isdigit():
                    return int(value)
                return None
        return None

    def _logs_read_ok(self, state, criteria):
        if not criteria.get('requires_logs_read', False):
            return True
        return state.env_vars.get('logs_read') == '1'

    def _clamp_score(self, value):
        return min(self.SUCCESS_SCORE, max(self.MIN_SCORE, float(value)))
