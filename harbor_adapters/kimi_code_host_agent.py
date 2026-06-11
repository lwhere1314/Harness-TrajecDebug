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
        upload_mode: str = "single_file",
        clear_app_before_upload: bool = True,
        post_upload_timeout_sec: int = 180,
        stop_after_path: str | None = None,
        upload_on_timeout: bool = False,
        *args,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, *args, **kwargs)
        self.kimi_code_root = Path(kimi_code_root).expanduser().absolute()
        self.node_bin = Path(node_bin).expanduser().resolve() if "/" in node_bin else Path(node_bin)
        self.prompt_timeout_sec = int(prompt_timeout_sec)
        self.previous_failure_path = (
            Path(previous_failure_path).expanduser().absolute()
            if previous_failure_path
            else None
        )
        self.include_env_snapshot = bool(include_env_snapshot)
        if upload_mode not in {"single_file", "workspace"}:
            raise ValueError("upload_mode must be 'single_file' or 'workspace'")
        self.upload_mode = upload_mode
        self.clear_app_before_upload = bool(clear_app_before_upload)
        self.post_upload_timeout_sec = int(post_upload_timeout_sec)
        self.stop_after_path = stop_after_path
        self.upload_on_timeout = bool(upload_on_timeout)
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
            "upload_mode": self.upload_mode,
            "clear_app_before_upload": self.clear_app_before_upload,
            "post_upload_timeout_sec": self.post_upload_timeout_sec,
            "stop_after_path": self.stop_after_path,
            "upload_on_timeout": self.upload_on_timeout,
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
        workspace = (self.logs_dir / "host-workspace").absolute()
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)

        await environment.download_dir("/app", workspace)

        snapshot = (
            await self._gather_env_snapshot(environment)
            if self.include_env_snapshot
            else ""
        )
        failure_context = self._read_previous_failure()
        prompt = self._build_prompt(
            instruction,
            workspace,
            env_snapshot=snapshot,
            failure_context=failure_context,
        )
        (self.logs_dir / "prompt.txt").write_text(prompt)
        if snapshot:
            (self.logs_dir / "env-snapshot.txt").write_text(snapshot)
        if failure_context:
            (self.logs_dir / "previous-failure.txt").write_text(failure_context)

        started_at = _iso_now()
        target_path = (
            workspace / "run.py"
            if self.upload_mode == "single_file"
            else (workspace / self.stop_after_path if self.stop_after_path else None)
        )
        result = await self._run_kimi(prompt, target_path)
        finished_at = _iso_now()

        (self.logs_dir / "kimi-stdout.txt").write_text(result["stdout"])
        (self.logs_dir / "kimi-stderr.txt").write_text(result["stderr"])
        (self.logs_dir / "kimi-return-code.txt").write_text(str(result["return_code"]))

        if self.upload_mode == "single_file":
            uploaded_path, sanity_return_code = await self._upload_single_file(environment, workspace)
        else:
            uploaded_path, sanity_return_code = await self._upload_workspace(environment, workspace)

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
            "upload_mode": self.upload_mode,
            "uploaded_path": uploaded_path,
            "kimi_return_code": result["return_code"],
            "kimi_timed_out": result.get("timed_out", False),
            "sanity_return_code": sanity_return_code,
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
        workspace: Path,
        env_snapshot: str = "",
        failure_context: str = "",
    ) -> str:
        if self.upload_mode == "single_file":
            target_run_py = workspace / "run.py"
            header = (
                "You are solving a Harbor benchmark task. Create exactly one file at "
                f"`{target_run_py}`. This file will be uploaded to `/app/run.py` "
                "inside the task container before verification. Do not create `run.py` "
                "in the current repository directory. Do not run tests. After writing "
                "the file, respond with DONE and stop.\n\n"
            )
        else:
            header = (
                "You are solving a Harbor benchmark task using a host-side copy of "
                f"the container `/app` directory at `{workspace}`. Modify files only "
                "inside that workspace so that, after the entire workspace is uploaded "
                "back to `/app`, the official verifier will pass. Do not modify this "
                f"repository outside that workspace. If the task instruction says to "
                f"create `/app/foo`, create `{workspace}/foo` in the host workspace. "
                "Do not rely on undeclared host-only "
                "packages or state; the verifier runs in the task container. If the task "
                "requires commands to run inside the task container after files are "
                f"uploaded, create `{workspace}/.kimi-post-upload.sh`; it will be run "
                "from `/app` in the container before verification. Use that script for "
                "container-side installs, code generation, or launching background "
                "services, and make sure it exits promptly after starting any background "
                "processes. Do not run the official verifier. When all needed files are "
                "in place, respond with DONE and stop.\n\n"
            )
            if self.stop_after_path:
                header += (
                    f"The adapter may stop once `{workspace / self.stop_after_path}` "
                    "exists and is stable, so write the final answer there only when it "
                    "is ready to upload.\n\n"
                )

        parts = [header + "Original task instruction:\n" + f"{instruction}"]
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
            "echo '@@ENV@@' && "
            "(env | sort | grep -Ei '^(http|https|all|no)_proxy=|^GRPC_' || true) && "
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
        if "ENV" in sections:
            env_lines = [
                line.strip()
                for line in sections["ENV"].strip().splitlines()
                if line.strip()
            ]
            if env_lines:
                parts.append("Proxy/gRPC environment: " + "; ".join(env_lines))
        if "MEM" in sections and sections["MEM"].strip():
            parts.append(f"Memory: {sections['MEM'].strip()}")

        return "[Environment Snapshot]\n" + "\n".join(parts) if parts else ""

    def _read_previous_failure(self) -> str:
        if not self.previous_failure_path:
            return ""
        text = self.previous_failure_path.read_text(errors="replace").strip()
        return text[-20000:]

    async def _upload_single_file(
        self,
        environment: BaseEnvironment,
        workspace: Path,
    ) -> tuple[str, int | None]:
        run_py = self._find_run_py(workspace)
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
        return "/app/run.py", sanity.return_code

    async def _upload_workspace(
        self,
        environment: BaseEnvironment,
        workspace: Path,
    ) -> tuple[str, int | None]:
        if not any(workspace.iterdir()):
            raise FileNotFoundError(f"Kimi Code left workspace empty: {workspace}")

        await environment.exec("mkdir -p /app")
        if self.clear_app_before_upload:
            await environment.exec("find /app -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +")
        await environment.upload_dir(workspace, "/app")
        normalize = await environment.exec(
            """
if command -v chown >/dev/null 2>&1; then
  chown -R "$(id -u):$(id -g)" /app || true
fi
if command -v git >/dev/null 2>&1; then
  git config --global --add safe.directory /app || true
  find /app -name .git -type d -prune -print 2>/dev/null | while IFS= read -r gitdir; do
    repo_dir="${gitdir%/.git}"
    git config --global --add safe.directory "$repo_dir" || true
  done
fi
""",
            cwd="/app",
            timeout_sec=120,
        )
        (self.logs_dir / "workspace-normalize-return-code.txt").write_text(
            str(normalize.return_code)
        )
        if normalize.stdout:
            (self.logs_dir / "workspace-normalize-stdout.txt").write_text(normalize.stdout)
        if normalize.stderr:
            (self.logs_dir / "workspace-normalize-stderr.txt").write_text(normalize.stderr)

        post_upload_return_code = await self._run_post_upload_script(environment)

        sanity = await environment.exec(
            "find /app -maxdepth 2 -mindepth 1 -printf '%M %p\\n' | sort | head -80",
            cwd="/app",
            timeout_sec=15,
        )
        (self.logs_dir / "workspace-upload-list-return-code.txt").write_text(
            str(sanity.return_code)
        )
        if sanity.stdout:
            (self.logs_dir / "workspace-upload-list.txt").write_text(sanity.stdout)
        if sanity.stderr:
            (self.logs_dir / "workspace-upload-list-stderr.txt").write_text(sanity.stderr)
        return "/app", post_upload_return_code if post_upload_return_code is not None else sanity.return_code

    async def _run_post_upload_script(self, environment: BaseEnvironment) -> int | None:
        exists = await environment.exec("test -f /app/.kimi-post-upload.sh", timeout_sec=10)
        (self.logs_dir / "post-upload-present-return-code.txt").write_text(
            str(exists.return_code)
        )
        if exists.return_code != 0:
            return None

        result = await environment.exec(
            "chmod +x /app/.kimi-post-upload.sh && /bin/sh /app/.kimi-post-upload.sh",
            cwd="/app",
            timeout_sec=self.post_upload_timeout_sec,
        )
        (self.logs_dir / "post-upload-return-code.txt").write_text(str(result.return_code))
        if result.stdout:
            (self.logs_dir / "post-upload-stdout.txt").write_text(result.stdout)
        if result.stderr:
            (self.logs_dir / "post-upload-stderr.txt").write_text(result.stderr)
        if result.return_code != 0:
            raise RuntimeError(
                f"Post-upload script failed with {result.return_code}; "
                f"see {self.logs_dir / 'post-upload-stderr.txt'}"
            )
        return result.return_code

    async def _run_kimi(self, prompt: str, target_path: Path | None) -> dict[str, object]:
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
            if target_path is None:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.prompt_timeout_sec,
                )
                stopped_after_target = False
            else:
                stdout, stderr, stopped_after_target = await asyncio.wait_for(
                    self._communicate_until_target(process, target_path),
                    timeout=self.prompt_timeout_sec,
                )
        except asyncio.TimeoutError:
            self._terminate_process_group(process)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            except Exception:
                stdout, stderr = b"", b""
                await process.wait()
            if not self.upload_on_timeout:
                raise
            return {
                "return_code": process.returncode if process.returncode is not None else -15,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "stopped_after_target": False,
                "timed_out": True,
            }

        return {
            "return_code": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "stopped_after_target": stopped_after_target,
            "timed_out": False,
        }

    async def _communicate_until_target(
        self,
        process: asyncio.subprocess.Process,
        target_path: Path,
    ) -> tuple[bytes, bytes, bool]:
        communicate_task = asyncio.create_task(process.communicate())
        target_seen = False
        stable_size: int | None = None
        stable_count = 0

        while not communicate_task.done():
            if target_path.exists():
                size = target_path.stat().st_size
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
                "execution_mode": f"host-kimi-upload-{self.upload_mode}",
            },
        }
        (self.logs_dir / "trajectory.json").write_text(format_trajectory_json(trajectory))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
