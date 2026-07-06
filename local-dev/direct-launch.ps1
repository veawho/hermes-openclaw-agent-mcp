$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $dir
Write-Host "Launching server.py via python3 stdio MCP..." -ForegroundColor Cyan
& python3 "-u" (Join-Path $root "server.py")
