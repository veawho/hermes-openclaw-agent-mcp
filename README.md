# hermes-openclaw-agent-mcp

Thin stdio MCP server that lets Hermes drive WSL-resident
[OpenClaw](https://github.com/openclaw/openclaw) agent subagents as if they
were first-class MCP tools.

## Why

The `windows-wsl` topology ships 3 layers:

```
win-hermes  →  wsl-hermes (MCP server, channels bridge)
                 →  wsl-openclaw (OpenClaw gateway on :18789)
                      →  openclaw-agent  (cwd=/mnt/c/.../.gemini/antigravity)
```

OpenClaw's built-in `mcp serve` only exposes a **channels bridge** (9
conversations/messages tools), it does NOT expose an "agent spawn" tool. So
Hermes has no MCP-path way to dispatch a task to an OpenClaw subagent.

This wrapper closes that gap with 4 tools around `openclaw agent --local
--message ...`:

| Tool                          | Purpose                                        |
|-------------------------------|------------------------------------------------|
| `openclaw_agent_version`      | Report installed OpenClaw version (for upgrade detection) |
| `openclaw_agent_spawn`        | Fire-and-forget or block-and-wait for a subagent run |
| `openclaw_agent_status`       | Is a spawned PID still alive?                  |
| `openclaw_agent_cancel`       | SIGTERM a spawned PID                          |

## Installation (via Hermes catalog)

Set `HERMES_OPTIONAL_MCPS` to the directory that contains this repo's
`manifest.yaml`, then:

```bash
hermes mcp catalog                # should list "openclaw_agent"
hermes mcp install openclaw_agent # clone + bootstrap + write config.yaml
# restart Hermes so the new MCP tools register
```

`spawn` accepts a `model` arg so you can route around a dead Gemini key:

```python
mcp_openclaw_agent_spawn(
    task="find all *.md newer than 2026-07-01 in /mnt/g/agent/knowledge",
    model="minimax-cn/MiniMax-M2.5-highspeed",
    background=True,
)
```

## Upgrade safety

* **Hermes upgrade (`pip install --upgrade hermes-agent`)** — wrapper lives
  outside the hermes-agent package tree at
  `~/.hermes/mcp-installs/openclaw_agent/`. Re-running `hermes mcp install
  openclaw_agent --reinstall` re-clones the pinned `ref:` from the manifest.
* **OpenClaw upgrade (`npm install -g openclaw@latest`)** — wrapper resolves
  the dist path via `npm root -g` at every call, so version bumps are
  transparent. If OpenClaw renames `agent` → `agent run`, update
  `server.py` line ~84 (one place) and bump the manifest `ref:`.

## Files

* `server.py`     — the MCP server (60 lines of tool wrapping)
* `manifest.yaml` — Hermes catalog entry
* `scripts/`      — manual launcher if you don't want to use the catalog
