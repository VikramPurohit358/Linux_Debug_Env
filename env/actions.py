"""Action parsing and execution."""


class ActionParser:
    """Parse actions from agent input."""
    
    def parse(self, action):
        """Parse action string into structured action dict."""
        action_text = "" if action is None else str(action).strip()

        if action_text.startswith("kill_port "):
            payload = action_text.replace("kill_port ", "", 1).strip()
            port = int(payload) if payload.isdigit() else None
            return {"type": "kill_port", "args": {"port": port}}

        if ":" not in action_text:
            return {"type": "invalid", "args": {"raw": action_text}}

        action_type, payload = action_text.split(":", 1)
        action_type = action_type.strip()
        payload = payload.strip()

        if action_type == "run_command":
            return {"type": "run_command", "args": {"command": payload}}

        if action_type == "read_file":
            return {"type": "read_file", "args": {"path": payload}}

        if action_type == "write_file":
            if "|" not in payload:
                return {
                    "type": "write_file",
                    "args": {"path": payload, "content": None},
                }
            path, content = payload.split("|", 1)
            return {
                "type": "write_file",
                "args": {"path": path.strip(), "content": content},
            }

        if action_type == "restart_service":
            return {"type": "restart_service", "args": {"service": payload}}

        if action_type == "kill_port":
            port = int(payload) if payload.isdigit() else None
            return {"type": "kill_port", "args": {"port": port}}

        if action_type == "check_status":
            return {"type": "check_status", "args": {"service": payload}}

        return {"type": "invalid", "args": {"raw": action_text}}
    
    def validate(self, action):
        """Validate parsed action and required arguments."""
        action_type = action.get("type")
        args = action.get("args", {})

        if action_type == "run_command":
            command = (args.get("command") or "").strip()
            if not command:
                return False, "run_command requires a command"
            if command.startswith("systemctl status "):
                service = command.replace("systemctl status ", "", 1).strip()
                if service:
                    return True, ""
            if command.startswith("cat "):
                path = command.replace("cat ", "", 1).strip()
                if path:
                    return True, ""
            if command.startswith("kill_port "):
                port_text = command.replace("kill_port ", "", 1).strip()
                if port_text:
                    return True, ""
            return False, "unsupported run_command"

        if action_type == "read_file":
            path = (args.get("path") or "").strip()
            if not path:
                return False, "read_file requires a path"
            return True, ""

        if action_type == "write_file":
            path = (args.get("path") or "").strip()
            content = args.get("content")
            if not path:
                return False, "write_file requires a path"
            if content is None:
                return False, "write_file requires <path>|<content>"
            return True, ""

        if action_type == "kill_port":
            port = args.get("port")
            if isinstance(port, int):
                return True, ""
            return False, "kill_port requires an integer port"

        if action_type in ("restart_service", "check_status"):
            service = (args.get("service") or "").strip()
            if not service:
                return False, f"{action_type} requires a service"
            return True, ""

        return False, "unsupported action format"


class ActionExecutor:
    """Execute actions on system state."""
    
    def __init__(self, state=None):
        """Initialize with optional state reference."""
        self.state = state
    
    def set_state(self, state):
        """Set state reference after init."""
        self.state = state
    
    def execute(self, action):
        """Execute parsed action and return Linux-like output/error."""
        try:
            if self.state is None:
                return {
                    "output": "",
                    "error": "state unavailable",
                }

            action_type = action.get("type")
            args = action.get("args", {})

            if action_type == "run_command":
                return self._execute_run_command(args.get("command", ""))

            if action_type == "read_file":
                path = args.get("path", "")
                return self._read_file(path)

            if action_type == "write_file":
                path = args.get("path", "")
                content = args.get("content", "")
                self.state.update_file(path, content)
                return {
                    "output": f"Wrote {len(content)} bytes to {path}",
                    "error": "",
                }

            if action_type == "kill_port":
                port = args.get("port")
                if port in self.state.ports and self.state.ports.get(port) == "occupied":
                    self.state.update_port(port, "free")
                    return {
                        "output": f"Freed port {port}",
                        "error": "",
                    }
                return {
                    "output": "",
                    "error": f"Port {port} is not in use",
                }

            if action_type == "restart_service":
                service = args.get("service", "")
                if service not in self.state.services:
                    return {
                        "output": "",
                        "error": f"Service '{service}' not found",
                    }

                return self._restart_service(service)

            if action_type == "check_status":
                service = args.get("service", "")
                status = self.state.services.get(service)
                if status is None:
                    return {
                        "output": "",
                        "error": f"Service '{service}' not found",
                    }
                if status == "running":
                    status_output = f"{service} service is active (running)"
                else:
                    status_output = f"{service} service is inactive (dead)"
                return {
                    "output": status_output,
                    "error": "",
                }

            return {
                "output": "",
                "error": "unsupported action type",
            }
        except Exception as exc:
            return {
                "output": "",
                "error": f"execution failed: {exc}",
            }

    def _execute_run_command(self, command):
        """Execute supported run_command subset."""
        command = (command or "").strip()

        if command.startswith("systemctl status "):
            service = command.replace("systemctl status ", "", 1).strip()
            status = self.state.services.get(service)
            if status is None:
                return {
                    "output": "",
                    "error": f"Unit {service}.service could not be found.",
                }
            active_line = "active (running)" if status == "running" else "inactive (dead)"
            output = (
                f"● {service}.service - Mock Service\n"
                f"   Loaded: loaded (/etc/systemd/system/{service}.service)\n"
                f"   Active: {active_line}\n"
                f"   Docs: man:{service}(8)"
            )
            return {"output": output, "error": ""}

        if command.startswith("cat "):
            path = command.replace("cat ", "", 1).strip()
            return self._read_file(path)

        if command.startswith("kill_port "):
            port_text = command.replace("kill_port ", "", 1).strip()
            if not port_text.isdigit():
                return {
                    "output": "",
                    "error": "Invalid port",
                }

            port = int(port_text)
            if port in self.state.ports:
                self.state.update_port(port, "free")
                return {
                    "output": f"Freed port {port}",
                    "error": "",
                }

            return {
                "output": "",
                "error": "Invalid port",
            }

        return {
            "output": "",
            "error": "unsupported run_command",
        }

    def _read_file(self, path):
        """Read file contents from state."""
        path = (path or "").strip()
        if path == "/var/log/app.log":
            self.state.update_env("logs_read", "1")
        if path in self.state.files:
            return {"output": self.state.files[path], "error": ""}
        return {
            "output": "",
            "error": f"cat: {path}: No such file or directory",
        }

    def _restart_service(self, service):
        """Restart service based on config PORT and port occupancy."""
        config_path = "/etc/app.conf"
        config_content = self.state.files.get(config_path, "")
        port = self._extract_port(config_content)

        if port is None:
            error_message = "ERROR: Invalid PORT configuration"
            self.state.update_service(service, "stopped")
            self.state.update_file("/var/log/app.log", error_message)
            return {
                "output": f"Job for {service}.service failed.",
                "error": f"Failed to restart {service}: port is occupied",
            }

        port_status = self.state.ports.get(port, "free")
        if port_status == "occupied":
            error_message = f"ERROR: Port {port} already in use"
            self.state.update_service(service, "stopped")
            self.state.update_file("/var/log/app.log", error_message)
            return {
                "output": f"Job for {service}.service failed.",
                "error": f"Failed to restart {service}: port is occupied",
            }

        self.state.update_service(service, "running")
        return {
            "output": f"Restarted {service}. Service is running.",
            "error": "",
        }

    def _extract_port(self, config_content):
        """Extract integer PORT value from config text like 'PORT=9999'."""
        for line in str(config_content).splitlines():
            line = line.strip()
            if line.startswith("PORT="):
                value = line.split("=", 1)[1].strip()
                if value.isdigit():
                    return int(value)
                return None
        return None
