#!/usr/bin/env python3
"""CapsuleLab Remote Agent — lightweight Docker management HTTP server.

Deploy on remote machines to enable structured remote execution.
Start: python3 capsulelab_agent.py --port 8900
"""

import argparse
import json
import subprocess
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler


class AgentHandler(BaseHTTPRequestHandler):
    def _json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cmd(self, args: list[str], timeout: int = 120) -> dict:
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "exit_code": result.returncode,
            }
        except FileNotFoundError:
            return {"ok": False, "error": "Command not found"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Timed out after {timeout}s"}

    def do_GET(self):
        if self.path == "/health":
            docker = shutil.which("docker") is not None
            return self._json({"ok": True, "docker": docker})

        if self.path == "/docker/info":
            return self._json(self._cmd(["docker", "info", "--format", "{{.ServerVersion}}"]))

        if self.path == "/docker/ps":
            result = self._cmd(["docker", "ps", "-a", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}"])
            containers = []
            if result["ok"]:
                for line in result["stdout"].split("\n"):
                    if line.strip():
                        parts = line.split("\t")
                        containers.append({"id": parts[0], "name": parts[1], "status": parts[2]})
            return self._json({"ok": True, "containers": containers})

        if self.path.startswith("/docker/logs/"):
            name = self.path.split("/docker/logs/")[1]
            return self._json(self._cmd(["docker", "logs", "--tail", "100", name], timeout=30))

        if self.path.startswith("/docker/inspect/"):
            name = self.path.split("/docker/inspect/")[1]
            return self._json(self._cmd(["docker", "inspect", name], timeout=15))

        self._json({"error": "Not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/docker/run":
            name = body.get("name", "")
            image = body.get("image", "")
            gpu = body.get("gpu", False)
            project_path = body.get("project_path", "")
            ports = body.get("ports", [])
            args_list = ["docker", "run", "-d", "--name", name]
            if gpu:
                args_list.extend(["--gpus", "all"])
            if project_path:
                args_list.extend(["-v", f"{project_path}:/workspace", "-w", "/workspace"])
            for p in ports:
                args_list.extend(["-p", p])
            args_list.extend([image, "sleep", "infinity"])
            return self._json(self._cmd(args_list, timeout=120))

        if self.path == "/docker/stop":
            name = body.get("name", "")
            self._cmd(["docker", "stop", name])
            return self._json(self._cmd(["docker", "rm", name], timeout=60))

        if self.path == "/docker/exec":
            name = body.get("name", "")
            command = body.get("command", "")
            detach = body.get("detach", False)
            args_list = ["docker", "exec"]
            if detach:
                args_list.append("-d")
            args_list.extend([name, "sh", "-c", command])
            return self._json(self._cmd(args_list, timeout=120))

        if self.path == "/docker/build":
            project_path = body.get("project_path", ".")
            dockerfile = body.get("dockerfile", "Dockerfile")
            image = body.get("image", "app:dev")
            return self._json(self._cmd(
                ["docker", "build", "-f", dockerfile, "-t", image, project_path],
                timeout=600,
            ))

        if self.path == "/gpu/check":
            nvidia = shutil.which("nvidia-smi") is not None
            if not nvidia:
                return self._json({"ok": True, "gpu": False, "error": "nvidia-smi not found"})
            result = self._cmd(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], timeout=15)
            return self._json({**result, "gpu": result["ok"]})

        self._json({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="CapsuleLab Remote Agent")
    parser.add_argument("--port", type=int, default=8900, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), AgentHandler)
    print(f"CapsuleLab Agent listening on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
