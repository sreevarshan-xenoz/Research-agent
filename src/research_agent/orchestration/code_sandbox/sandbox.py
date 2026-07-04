from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    """Result from executing code in the sandbox."""
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    success: bool
    sandbox_type: str  # "docker" or "subprocess"


@dataclass
class SandboxConfig:
    """Configuration for the code execution sandbox."""
    image_python: str = "python:3.11-slim"
    image_r: str = "rocker/r-ver:4.3"
    image_julia: str = "julia:1.10"
    container_timeout: int = 60
    memory_limit_mb: int = 512
    max_output_chars: int = 100_000
    work_dir: str = "/tmp/sandbox_work"
    pool_size: int = 2
    pool_idle_timeout: int = 300  # seconds before idle containers are stopped


LANGUAGE_IMAGE_MAP: dict[str, str] = {
    "python": "python:3.11-slim",
    "r": "rocker/r-ver:4.3",
    "julia": "julia:1.10",
}


LANGUAGE_COMMAND_MAP: dict[str, list[str]] = {
    "python": ["python", "-c"],
    "r": ["Rscript", "-e"],
    "julia": ["julia", "-e"],
}


class DockerSandbox:
    """Sandboxed code execution environment.

    Uses Docker when available (docker Python SDK), with graceful fallback
    to local subprocess execution when Docker is not installed or running.
    """

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()
        self._docker_available: bool | None = None  # Lazily checked
        self._docker_client: Any = None
        self._warm_pool: dict[str, list[Any]] = {
            "python": [],
            "r": [],
            "julia": [],
        }
        self._pool_locks: dict[str, asyncio.Lock] = {
            lang: asyncio.Lock() for lang in self._warm_pool
        }
        self._shutdown_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Docker availability detection
    # ------------------------------------------------------------------

    @property
    def docker_available(self) -> bool:
        """Check if Docker is available (lazy, cached)."""
        if self._docker_available is None:
            self._docker_available = self._check_docker()
        return self._docker_available

    def _check_docker(self) -> bool:
        """Probe for Docker connectivity."""
        try:
            import docker  # type: ignore[import-untyped]
            client = docker.from_env()
            client.ping()
            self._docker_client = client
            logger.info("Docker sandbox: Docker is available")
            return True
        except Exception:
            logger.info("Docker sandbox: Docker not available, using subprocess fallback")
            self._docker_client = None
            return False

    # ------------------------------------------------------------------
    # Image management
    # ------------------------------------------------------------------

    async def ensure_image(self, language: str = "python") -> bool:
        """Pull the Docker image for the given language if not present.

        Returns True if image is available (either already present or
        successfully pulled). No-op when Docker is unavailable.
        """
        if not self.docker_available or self._docker_client is None:
            return False

        image_tag = LANGUAGE_IMAGE_MAP.get(language, LANGUAGE_IMAGE_MAP["python"])
        try:
            self._docker_client.images.get(image_tag)
            logger.debug("Image %s already present", image_tag)
            return True
        except Exception:
            pass

        logger.info("Pulling image %s (this may take a while)...", image_tag)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self._docker_client.images.pull(image_tag),
            )
            logger.info("Image %s pulled successfully", image_tag)
            return True
        except Exception as exc:
            logger.warning("Failed to pull image %s: %s", image_tag, exc)
            return False

    # ------------------------------------------------------------------
    # Container lifecycle (warm pool)
    # ------------------------------------------------------------------

    async def _create_container(self, language: str) -> Any | None:
        """Create a new warm container for the given language."""
        if not self.docker_available or self._docker_client is None:
            return None

        image_tag = LANGUAGE_IMAGE_MAP.get(language, LANGUAGE_IMAGE_MAP["python"])
        try:
            container = self._docker_client.containers.create(
                image=image_tag,
                command=["sleep", "3600"],  # Keep alive
                detach=True,
                mem_limit=f"{self.config.memory_limit_mb}m",
                working_dir=self.config.work_dir,
                network_disabled=False,
                stdin_open=True,
                tty=False,
            )
            container.start()
            logger.debug("Created warm container for %s: %s", language, container.id[:12])
            return container
        except Exception as exc:
            logger.warning("Failed to create warm container for %s: %s", language, exc)
            return None

    async def _get_container(self, language: str) -> Any | None:
        """Pop a container from the warm pool or create a new one."""
        lock = self._pool_locks.get(language)
        if lock is None:
            return None

        async with lock:
            pool = self._warm_pool.get(language, [])
            if pool:
                return pool.pop(0)
        return await self._create_container(language)

    async def _return_container(self, container: Any, language: str) -> None:
        """Return a container to the warm pool (if pool not full)."""
        lock = self._pool_locks.get(language)
        if lock is None:
            try:
                container.stop()
                container.remove()
            except Exception:
                pass
            return

        async with lock:
            pool = self._warm_pool.get(language, [])
            if len(pool) < self.config.pool_size:
                pool.append(container)
                return

        # Pool is full — stop and remove
        try:
            container.stop()
            container.remove()
        except Exception:
            pass

    async def prewarm_pool(self) -> None:
        """Pre-warm the container pool for all supported languages."""
        if not self.docker_available:
            return
        for language in ("python", "r", "julia"):
            if await self.ensure_image(language):
                for _ in range(self.config.pool_size):
                    await self._create_container(language)

    async def shutdown_pool(self) -> None:
        """Stop and remove all warm pool containers."""
        self._shutdown_event.set()
        for language, pool in self._warm_pool.items():
            lock = self._pool_locks.get(language)
            if lock:
                async with lock:
                    for container in pool:
                        try:
                            container.stop()
                            container.remove()
                        except Exception:
                            pass
                    pool.clear()

    # ------------------------------------------------------------------
    # Code execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int | None = None,
    ) -> SandboxResult:
        """Execute code in the sandbox.

        Uses Docker when available, falls back to local subprocess.
        Supports Python, R, and Julia.
        """
        if timeout is None:
            timeout = self.config.container_timeout

        if self.docker_available:
            return await self._execute_docker(code, language, timeout)
        return await self._execute_subprocess(code, language, timeout)

    async def _execute_docker(
        self,
        code: str,
        language: str,
        timeout: int,
    ) -> SandboxResult:
        """Execute code in a Docker container."""
        container = await self._get_container(language)
        if container is None:
            # Fall back to subprocess if container creation failed
            logger.warning("Docker container unavailable, falling back to subprocess")
            return await self._execute_subprocess(code, language, timeout)

        start_time = time.monotonic()
        try:
            # Write code to a temp file inside the container
            exec_cmd = LANGUAGE_COMMAND_MAP.get(language, LANGUAGE_COMMAND_MAP["python"])
            # For multi-line code, write to file and execute
            full_cmd = ["/bin/sh", "-c", f"cat > /tmp/script.py << 'CODEOF'\n{code}\nCODEOF\n{exec_cmd[0]} /tmp/script.py"]

            exec_result = container.exec_run(
                cmd=full_cmd,
                demux=True,
                timeout=timeout,
            )

            duration = time.monotonic() - start_time
            exit_code = exec_result.exit_code
            output = exec_result.output

            stdout_bytes, stderr_bytes = output if isinstance(output, tuple) else (output, b"")
            stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")[:self.config.max_output_chars]
            stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")[:self.config.max_output_chars]

            result = SandboxResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code or 0,
                duration_seconds=round(duration, 3),
                success=exit_code == 0,
                sandbox_type="docker",
            )
        except Exception as exc:
            duration = time.monotonic() - start_time
            result = SandboxResult(
                stdout="",
                stderr=str(exc),
                exit_code=-1,
                duration_seconds=round(duration, 3),
                success=False,
                sandbox_type="docker",
            )
        finally:
            await self._return_container(container, language)

        return result

    async def _execute_subprocess(
        self,
        code: str,
        language: str,
        timeout: int,
    ) -> SandboxResult:
        """Execute code via local subprocess (fallback when Docker unavailable)."""
        executable = sys.executable if language == "python" else shutil.which(language)
        if executable is None:
            return SandboxResult(
                stdout="",
                stderr=f"Language '{language}' not found on this system",
                exit_code=-1,
                duration_seconds=0.0,
                success=False,
                sandbox_type="subprocess",
            )

        start_time = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                executable,
                "-c" if language == "python" else "-e",
                code,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout,
                )
                stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")[:self.config.max_output_chars]
                stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")[:self.config.max_output_chars]
                exit_code = proc.returncode or 0
                success = exit_code == 0
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                stdout = ""
                stderr = f"Execution timed out after {timeout} seconds"
                exit_code = -1
                success = False

            duration = time.monotonic() - start_time
            return SandboxResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_seconds=round(duration, 3),
                success=success,
                sandbox_type="subprocess",
            )
        except Exception as exc:
            duration = time.monotonic() - start_time
            return SandboxResult(
                stdout="",
                stderr=str(exc),
                exit_code=-1,
                duration_seconds=round(duration, 3),
                success=False,
                sandbox_type="subprocess",
            )
