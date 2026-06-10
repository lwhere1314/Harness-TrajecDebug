"""Harbor adapter that runs this checkout's Kimi Code CLI on the host."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import shutil
from datetime import datetime, timezone
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.utils.trajectory_utils import format_trajectory_json


class KimiCodeHostAgent(BaseAgent):
    """Run Kimi Code headlessly in a host workspace, then upload the result."""

    SUPPORTS_ATIF = True

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        kimi_code_root: str = "kimi-code",
        node_bin: str = "node",
        prompt_timeout_sec: int = 840,
        previous_failure_path: str | None = None,
        include_env_snapshot: bool = True,
        *args,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, *args, **kwargs)
        self.kimi_code_root = Path(kimi_code_root).expanduser().resolve()
        self.node_bin = Path(node_bin).expanduser().resolve() if "/" in node_bin else Path(node_bin)
        self.prompt_timeout_sec = int(prompt_timeout_sec)
        self.previous_failure_path = (
            Path(previous_failure_path).expanduser().resolve()
            if previous_failure_path
            else None
        )
        self.include_env_snapshot = bool(include_env_snapshot)
        self._version = self._read_version()

    @staticmethod
    def name() -> str:
        return "kimi-code"

    def version(self) -> str | None:
        return self._version

    async def setup(self, environment: BaseEnvironment) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        setup_dir = self.logs_dir / "setup"
        setup_dir.mkdir(parents=True, exist_ok=True)

        checks = {
            "kimi_code_root": str(self.kimi_code_root),
            "node_bin": str(self.node_bin),
            "dev_script": str(self._dev_script),
            "model_name": self.model_name,
            "previous_failure_path": (
                str(self.previous_failure_path) if self.previous_failure_path else None
            ),
            "include_env_snapshot": self.include_env_snapshot,
        }
        (setup_dir / "checks.json").write_text(json.dumps(checks, indent=2))

        if not self.kimi_code_root.exists():
            raise FileNotFoundError(f"Kimi Code root not found: {self.kimi_code_root}")
        if not self._dev_script.exists():
            raise FileNotFoundError(f"Kimi Code dev script not found: {self._dev_script}")
        if "/" in str(self.node_bin) and not self.node_bin.exists():
            raise FileNotFoundError(f"Node binary not found: {self.node_bin}")
        if self.previous_failure_path and not self.previous_failure_path.exists():
            raise FileNotFoundError(
                f"Previous failure file not found: {self.previous_failure_path}"
            )

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        workspace = (self.logs_dir / "host-workspace").resolve()
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)

        await environment.download_dir("/app", workspace)

        target_run_py = workspace / "run.py"
        snapshot = (
            await self._gather_env_snapshot(environment)
            if self.include_env_snapshot
            else ""
        )
        failure_context = self._read_previous_failure()
        prompt = self._build_prompt(
            instruction,
            target_run_py,
            env_snapshot=snapshot,
            failure_context=failure_context,
        )
        (self.logs_dir / "prompt.txt").write_text(prompt)
        if snapshot:
            (self.logs_dir / "env-snapshot.txt").write_text(snapshot)
        if failure_context:
            (self.logs_dir / "previous-failure.txt").write_text(failure_context)

        started_at = _iso_now()
        result = await self._run_kimi(prompt, target_run_py)
        finished_at = _iso_now()

        (self.logs_dir / "kimi-stdout.txt").write_text(result["stdout"])
        (self.logs_dir / "kimi-stderr.txt").write_text(result["stderr"])
        (self.logs_dir / "kimi-return-code.txt").write_text(str(result["return_code"]))

        run_py = self._find_run_py(workspace)
        if result["return_code"] != 0 and run_py is None:
            raise RuntimeError(
                f"Kimi Code exited with {result['return_code']}; "
                f"see {self.logs_dir / 'kimi-stderr.txt'}"
            )
        if run_py is None:
            raise FileNotFoundError(f"Kimi Code did not create run.py under {workspace}")

        await environment.exec("mkdir -p /app")
        await environment.upload_file(run_py, "/app/run.py")

        sanity = await environment.exec("python -m py_compile /app/run.py", cwd="/app")
        (self.logs_dir / "py-compile-return-code.txt").write_text(str(sanity.return_code))
        if sanity.stdout:
            (self.logs_dir / "py-compile-stdout.txt").write_text(sanity.stdout)
        if sanity.stderr:
            (self.logs_dir / "py-compile-stderr.txt").write_text(sanity.stderr)

        self._write_trajectory(
            instruction=instruction,
            prompt=prompt,
            stdout=result["stdout"],
            stderr=result["stderr"],
            return_code=result["return_code"],
            started_at=started_at,
            finished_at=finished_at,
        )
        context.metadata = {
            "host_workspace": str(workspace),
            "uploaded_file": "/app/run.py",
            "kimi_return_code": result["return_code"],
            "py_compile_return_code": sanity.return_code,
        }

    @property
    def _dev_script(self) -> Path:
        return self.kimi_code_root / "apps" / "kimi-code" / "scripts" / "dev.mjs"

    def _read_version(self) -> str:
        package_json = self.kimi_code_root / "apps" / "kimi-code" / "package.json"
        try:
            data = json.loads(package_json.read_text())
        except Exception:
            return "local-source"
        return str(data.get("version") or "local-source")

    def _build_prompt(
        self,
        instruction: str,
        target_run_py: Path,
        env_snapshot: str = "",
        failure_context: str = "",
    ) -> str:
        parts = [
            "You are solving a Harbor benchmark task. Create exactly one file at "
            f"`{target_run_py}`. This file will be uploaded to `/app/run.py` "
            "inside the task container before verification. Do not create `run.py` "
            "in the current repository directory. Do not run tests. After writing "
            "the file, respond with DONE and stop.\n\n"
            "Original task instruction:\n"
            f"{instruction}"
        ]
        if env_snapshot:
            parts.append(
                "\n\nMeta-Harness environment bootstrap:\n"
                "The following deterministic snapshot was gathered from the task "
                "container before you started. Use it to avoid spending steps on "
                "basic environment discovery.\n"
                f"{env_snapshot}"
            )
        if failure_context:
            parts.append(
                "\n\nMeta-Harness prior candidate feedback:\n"
                "A previous candidate for this same task failed verification. "
                "Use this failure signal to propose a corrected implementation; "
                "do not simply repeat the previous solution.\n"
                f"{failure_context}"
            )
        return "".join(parts)

    async def _gather_env_snapshot(self, environment: BaseEnvironment) -> str:
        bootstrap_cmd = (
            "echo '@@PWD@@' && pwd && "
            "echo '@@LS@@' && ls -la /app/ 2>/dev/null && "
            "echo '@@LANG@@' && "
            "(python3 --version 2>&1 || echo 'python3: not found') && "
            "(python --version 2>&1 || echo 'python: not found') && "
            "(node --version 2>&1 || echo 'node: not found') && "
            "echo '@@PKG@@' && "
            "(pip3 --version 2>&1 || echo 'pip3: not found') && "
            "(pip --version 2>&1 || echo 'pip: not found') && "
            "(uv --version 2>&1 || echo 'uv: not found') && "
            "echo '@@MEM@@' && free -h 2>/dev/null | head -2 || true"
        )
        try:
            result = await asyncio.wait_for(
                environment.exec(command=bootstrap_cmd, timeout_sec=15),
                timeout=20,
            )
        except Exception:
            return ""

        stdout = (result.stdout or "").strip()
        if not stdout:
            return ""

        sections: dict[str, str] = {}
        current_key: str | None = None
        current_lines: list[str] = []
        for line in stdout.splitlines():
            if line.startswith("@@") and line.endswith("@@"):
                if current_key:
                    sections[current_key] = "\n".join(current_lines)
                current_key = line.strip("@")
                current_lines = []
            else:
                current_lines.append(line)
        if current_key:
            sections[current_key] = "\n".join(current_lines)

        parts: list[str] = []
        if "PWD" in sections:
            parts.append(f"Working directory: {sections['PWD'].strip()}")
        if "LS" in sections:
            ls_lines = sections["LS"].strip().splitlines()
            if len(ls_lines) > 25:
                app_listing = "\n".join(ls_lines[:20])
                parts.append(
                    f"/app contents ({len(ls_lines)} entries):\n"
                    f"{app_listing}\n... ({len(ls_lines) - 20} more files)"
                )
            else:
                parts.append(f"/app contents:\n{sections['LS'].strip()}")
        if "LANG" in sections:
            lang_lines = [
                line.strip()
                for line in sections["LANG"].strip().splitlines()
                if line.strip()
            ]
            parts.append("Available languages/tools: " + "; ".join(lang_lines))
        if "PKG" in sections:
            pkg_lines = [
                line.strip()
                for line in sections["PKG"].strip().splitlines()
                if line.strip()
            ]
            parts.append("Package managers: " + "; ".join(pkg_lines))
        if "MEM" in sections and sections["MEM"].strip():
            parts.append(f"Memory: {sections['MEM'].strip()}")

        return "[Environment Snapshot]\n" + "\n".join(parts) if parts else ""

    def _read_previous_failure(self) -> str:
        if not self.previous_failure_path:
            return ""
        text = self.previous_failure_path.read_text(errors="replace").strip()
        return text[-20000:]

    async def _run_kimi(self, prompt: str, target_run_py: Path) -> dict[str, object]:
        env = os.environ.copy()
        node_dir = str(self.node_bin.parent) if "/" in str(self.node_bin) else ""
        if node_dir:
            env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")
        env["NO_COLOR"] = "1"

        command = [
            str(self.node_bin),
            str(self._dev_script),
            "--prompt",
            prompt,
            "--output-format",
            "stream-json",
        ]
        if self.model_name:
            command.extend(["--model", self.model_name])

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(self.kimi_code_root),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr, stopped_after_target = await asyncio.wait_for(
                self._communicate_until_target(process, target_run_py),
                timeout=self.prompt_timeout_sec,
            )
        except asyncio.TimeoutError:
            self._terminate_process_group(process)
            await process.wait()
            raise

        return {
            "return_code": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "stopped_after_target": stopped_after_target,
        }

    async def _communicate_until_target(
        self,
        process: asyncio.subprocess.Process,
        target_run_py: Path,
    ) -> tuple[bytes, bytes, bool]:
        communicate_task = asyncio.create_task(process.communicate())
        target_seen = False
        stable_size: int | None = None
        stable_count = 0

        while not communicate_task.done():
            if target_run_py.exists():
                size = target_run_py.stat().st_size
                if size > 0 and size == stable_size:
                    stable_count += 1
                else:
                    stable_size = size
                    stable_count = 0

                if stable_count >= 2:
                    target_seen = True
                    self._terminate_process_group(process)
                    break

            await asyncio.sleep(1)

        stdout, stderr = await communicate_task
        return stdout, stderr, target_seen

    @staticmethod
    def _terminate_process_group(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return

    @staticmethod
    def _find_run_py(workspace: Path) -> Path | None:
        candidates = [
            workspace / "run.py",
            workspace / "app" / "run.py",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        matches = sorted(workspace.rglob("run.py"))
        return matches[0] if matches else None

    def _write_trajectory(
        self,
        instruction: str,
        prompt: str,
        stdout: str,
        stderr: str,
        return_code: int,
        started_at: str,
        finished_at: str,
    ) -> None:
        trajectory = {
            "schema_version": "ATIF-v1.6",
            "session_id": self.logs_dir.parent.name,
            "agent": {
                "name": self.name(),
                "version": self.version() or "local-source",
                "model_name": self.model_name,
                "extra": {
                    "kimi_code_root": str(self.kimi_code_root),
                    "node_bin": str(self.node_bin),
                },
            },
            "steps": [
                {
                    "step_id": 1,
                    "timestamp": started_at,
                    "source": "user",
                    "message": instruction,
                },
                {
                    "step_id": 2,
                    "timestamp": finished_at,
                    "source": "agent",
                    "model_name": self.model_name,
                    "message": stdout[-12000:] if stdout else "Kimi Code completed.",
                    "extra": {
                        "prompt": prompt,
                        "stderr_tail": stderr[-12000:],
                        "return_code": return_code,
                    },
                },
            ],
            "extra": {
                "execution_mode": "host-kimi-upload-run.py",
            },
        }
        (self.logs_dir / "trajectory.json").write_text(format_trajectory_json(trajectory))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
