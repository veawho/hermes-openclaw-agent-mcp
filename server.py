#!/usr/bin/env python3
"""
openclaw_agent MCP server - Hermes ↔ WSL-resident OpenClaw subagents.

Wraps `openclaw agent --local --message ...` (or `--json` for blocking)
with model override, version detection, and background spawn semantics.

Tools exposed:
  - openclaw_agent_version()             -> installed openclaw version
  - openclaw_agent_spawn(task, model?, background=True) -> subprocess.Popen or run
  - openclaw_agent_status(pid)           -> alive?
  - openclaw_agent_cancel(pid)           -> SIGTERM

Transport: stdio MCP (compatible with hermes-agent optional-mcps catalog).
Installed via:  hermes mcp install openclaw_agent
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    sys.stderr.write("FATAL: `mcp` Python package not installed. Run `pip install mcp`.\n")
    sys.exit(2)

mcp = FastMCP("openclaw_agent")

# ─── Paths / Configuration ──────────────────────────────────────────────────

# workspace cwd that OpenClaw agent runs in — matches existing
# openclaw-agent child processes already observed on this host
DEFAULT_AGENT_CWD = "/mnt/c/Users/via54/.gemini/antigravity"


def _openclaw_dist_path() -> str:
    """Resolve openclaw dist/index.js via npm root -g (auto-handles version bumps)."""
    try:
        npm_root = subprocess.check_output(
            ["npm", "root", "-g"], text=True, timeout=10
        ).strip()
        return f"{npm_root}/openclaw/dist/index.js"
    except Exception as e:
        raise RuntimeError(
            f"Cannot resolve openclaw path via `npm root -g`: {e}. "
            "Is Node + npm + openclaw installed?"
        ) from e


def _run_openclaw(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    """Run openclaw dist/index.js with given args. Returns CompletedProcess."""
    dist = _openclaw_dist_path()
    cmd = ["node", dist, *args]
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=600
    )


# ─── MCP Tools ──────────────────────────────────────────────────────────────


@mcp.tool()
def version() -> str:
    """Return the installed openclaw version string (for upgrade checks)."""
    try:
        r = _run_openclaw(["--version"], cwd=DEFAULT_AGENT_CWD)
        if r.returncode == 0:
            return r.stdout.strip()
        return f"openclaw_error: rc={r.returncode} stderr={r.stderr[:200]}"
    except Exception as e:
        return f"version_unavailable: {e}"


@mcp.tool()
def spawn(
    task: str,
    model: str = "",
    background: bool = True,
    cwd: str = DEFAULT_AGENT_CWD,
) -> str:
    """Spawn an OpenClaw agent subagent to execute `task`.

    Args:
        task: the task description (passed to `openclaw agent --message`).
        model: optional model override (e.g. "minimax-cn/MiniMax-M2.5-highspeed").
               Empty = inherit OpenClaw config.
        background: True = return PID immediately (fire-and-forget).
                    False = block until agent finishes, return final JSON.
        cwd: working directory for the subagent (must be openclaw workspace).

    Returns:
        JSON: {"pid": <int>, "run_id": "oc_<pid>"} for background=True
              {"stdout": ..., "stderr": ..., "rc": int} for background=False
    """
    if not task.strip():
        return json.dumps({"error": "task cannot be empty"})

    args = ["agent", "--local", "--json"]
    if model.strip():
        args += ["--model", model.strip()]
    args += ["--message", task]

    if background:
        try:
            dist = _openclaw_dist_path()
            cmd = ["node", dist, *args]
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            return json.dumps(
                {"pid": proc.pid, "run_id": f"oc_{proc.pid}", "background": True}
            )
        except Exception as e:
            return json.dumps({"error": str(e)})
    else:
        try:
            r = _run_openclaw(args, cwd=cwd)
            return json.dumps(
                {
                    "rc": r.returncode,
                    "stdout": r.stdout[:8000],
                    "stderr": r.stderr[:2000],
                    "background": False,
                }
            )
        except subprocess.TimeoutExpired:
            return json.dumps({"error": "timeout_600s"})
        except Exception as e:
            return json.dumps({"error": str(e)})


@mcp.tool()
def status(pid: int) -> str:
    """Check whether a spawned subagent (by pid) is still running."""
    try:
        os.kill(pid, 0)
        return json.dumps({"alive": True, "pid": pid})
    except ProcessLookupError:
        return json.dumps({"alive": False, "pid": pid})
    except PermissionError:
        return json.dumps(
            {"alive": True, "pid": pid, "note": "permission_denied_but_alive"}
        )
    except Exception as e:
        return json.dumps({"error": str(e), "pid": pid})


@mcp.tool()
def cancel(pid: int) -> str:
    """Send SIGTERM to a spawned subagent. Use status() afterwards to confirm."""
    try:
        os.kill(pid, 15)  # SIGTERM
        return json.dumps({"sent": "SIGTERM", "pid": pid})
    except ProcessLookupError:
        return json.dumps({"error": "not_found", "pid": pid})
    except Exception as e:
        return json.dumps({"error": str(e), "pid": pid})


# ─── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()  # stdio MCP transport
