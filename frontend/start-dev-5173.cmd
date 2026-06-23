@echo off
setlocal

set "NODE_BIN=C:\Users\ez\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
set "PNPM_BIN=C:\Users\ez\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin"
set "PATH=%NODE_BIN%;%PNPM_BIN%;%PATH%"

cd /d "%~dp0"
"%PNPM_BIN%\pnpm.cmd" dev --host 0.0.0.0 --port 5173
