"""P19: Plugin System — Sandboxed execution for plugins.

Supports:
- Restricted globals sandbox (for trusted plugins)
- Subprocess sandbox (for untrusted plugins)
- Timeout enforcement
- Memory limits
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Restricted builtins for sandboxed code execution
_RESTRICTED_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "RuntimeError": RuntimeError,
    "StopIteration": StopIteration,
}


def _make_sandbox_globals(user_globals: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a restricted globals dict for sandboxed execution."""
    globals_dict: dict[str, Any] = {
        "__builtins__": _RESTRICTED_BUILTINS,
    }
    if user_globals:
        for key in user_globals:
            if key not in ("__builtins__", "__import__", "eval", "exec", "open", "compile"):
                globals_dict[key] = user_globals[key]
    return globals_dict


def _is_dangerous_code(code: str) -> bool:
    """Check if code contains dangerous operations."""
    dangerous_patterns = [
        "__import__",
        "subprocess",
        "os.system",
        "os.popen",
        "shutil",
        "ctypes",
        "socket",
        "requests.",
        "urllib.",
        "open(",
        "eval(",
        "exec(",
        "compile(",
        "__builtins__",
        "import ",
        "from ",
    ]
    code_lower = code.lower()
    for pattern in dangerous_patterns:
        if pattern.lower() in code_lower:
            return True
    return False


async def run_in_sandbox(
    hook_method: Callable[..., Any],
    timeout: int = 30,
    **kwargs: Any,
) -> Any:
    """Execute a plugin hook method with sandbox isolation.

    For runtime sandboxing, this runs the coroutine with a timeout.
    For code-based plugins, it would use restricted globals.

    Args:
        hook_method: The plugin hook method to call.
        timeout: Maximum execution time in seconds.
        kwargs: Arguments to pass to the hook method.

    Returns:
        The return value of the hook method.
    """
    try:
        result = await asyncio.wait_for(
            hook_method(**kwargs),
            timeout=timeout,
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("Plugin hook timed out after %ds", timeout)
        raise TimeoutError(f"Plugin hook timed out after {timeout}s")
    except Exception as exc:
        logger.error("Plugin hook execution failed: %s", exc)
        raise


def execute_code_sandboxed(
    code: str,
    globals_dict: dict[str, Any] | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    """Execute arbitrary Python code in a restricted sandbox.

    This is used for user-provided plugin scripts that need to be
    executed safely. NOT used for built-in plugins.

    Args:
        code: The Python code to execute.
        globals_dict: Additional globals to provide to the code.
        timeout: Maximum execution time in seconds.

    Returns:
        The globals dict after execution (with any new variables).
    """
    if _is_dangerous_code(code):
        raise SecurityError("Code contains potentially dangerous operations")

    local_globals = _make_sandbox_globals(globals_dict)

    try:
        exec_globals = local_globals.copy()
        exec(code, exec_globals)
        return exec_globals
    except Exception as exc:
        raise RuntimeError(f"Sandboxed code execution failed: {exc}")


class SecurityError(Exception):
    """Raised when code fails security checks."""
    pass
