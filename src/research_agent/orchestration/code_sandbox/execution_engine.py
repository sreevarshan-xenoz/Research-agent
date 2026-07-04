from __future__ import annotations

import logging
from dataclasses import dataclass, field

from research_agent.orchestration.code_sandbox.sandbox import DockerSandbox, SandboxResult
from research_agent.orchestration.code_sandbox.code_generator import VerificationCode

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing verification code for a claim."""
    claim_id: str
    sandbox_result: SandboxResult
    code: str
    language: str = "python"
    dependencies: list[str] = field(default_factory=list)
    install_errors: list[str] = field(default_factory=list)


class ExecutionEngine:
    """Executes verification code in the sandbox environment.

    Manages dependency installation and code execution, capturing
    stdout, stderr, exit codes, and timing.
    """

    def __init__(self, sandbox: DockerSandbox):
        self.sandbox = sandbox

    async def execute(
        self,
        code: VerificationCode,
        install_deps: bool = True,
    ) -> ExecutionResult:
        """Execute a verification code in the sandbox.

        Optionally installs dependencies before running the code.
        """
        install_errors: list[str] = []

        # Install dependencies if needed
        if install_deps and code.dependencies:
            for dep in code.dependencies:
                install_result = await self._install_dependency(dep)
                if not install_result.success:
                    install_errors.append(f"{dep}: {install_result.stderr[:200]}")

        # Execute the verification code
        sandbox_result = await self.sandbox.execute(
            code=code.code,
            language=code.language,
            timeout=code.estimated_runtime_seconds + 30,  # Buffer
        )

        return ExecutionResult(
            claim_id=code.claim_id,
            sandbox_result=sandbox_result,
            code=code.code,
            language=code.language,
            dependencies=code.dependencies,
            install_errors=install_errors,
        )

    async def _install_dependency(self, package: str) -> SandboxResult:
        """Install a pip package in the sandbox."""
        install_code = (
            f"import subprocess, sys; "
            f"subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '{package}'])"
        )
        return await self.sandbox.execute(
            code=install_code,
            language="python",
            timeout=120,
        )

    async def execute_batch(
        self,
        codes: list[VerificationCode],
    ) -> list[ExecutionResult]:
        """Execute multiple verification codes sequentially."""
        results: list[ExecutionResult] = []
        for code in codes:
            result = await self.execute(code)
            results.append(result)
        logger.info(
            "ExecutionEngine: executed %d verification scripts (%d succeeded)",
            len(results),
            sum(1 for r in results if r.sandbox_result.success),
        )
        return results
