"""Evaluation and rewards."""


class Grader:
    """Evaluates task completion and assigns rewards."""

    CONFIG_PATH = "/etc/app.conf"

    def grade(self, state, task):
        """Return deterministic score in {0.0, 0.5, 1.0}."""
        criteria = task.get_success_criteria()

        service_running = state.services.get("app") == criteria.get("service", "running")
        logs_ok = self._logs_read_ok(state, criteria)

        required_port = criteria.get("required_port", 8080)
        config_matches_required = self._config_port(state) == required_port

        allow_free_port_path = bool(criteria.get("allow_free_port_path", False))
        conflict_port = criteria.get("conflict_port", 9999)
        conflict_cleared = state.ports.get(conflict_port, "occupied") == "free"
        remediation_ok = config_matches_required or (allow_free_port_path and conflict_cleared)

        if service_running and logs_ok and remediation_ok:
            return 1.0

        if remediation_ok and not service_running:
            return 0.5

        if criteria.get("requires_logs_read", False) and logs_ok and remediation_ok:
            return 0.5

        return 0.0
    
    def evaluate(self, state, task):
        """Check if task is complete."""
        return self.grade(state, task) == 1.0

    def _config_port(self, state):
        """Extract configured PORT from /etc/app.conf."""
        content = state.files.get(self.CONFIG_PATH, "")
        for line in str(content).splitlines():
            line = line.strip()
            if line.startswith("PORT="):
                value = line.split("=", 1)[1].strip()
                if value.isdigit():
                    return int(value)
                return None
        return None

    def _logs_read_ok(self, state, criteria):
        """Whether task requires logs to be read and marker is present."""
        if not criteria.get("requires_logs_read", False):
            return True
        return state.env_vars.get("logs_read") == "1"
