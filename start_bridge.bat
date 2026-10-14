@echo off
title Universal IDE Bridge (Always Alive)
echo =========================================================
echo Starting Universal IDE Bridge...
echo Token: D4_PROJECT_MCP_SERVER
echo Root:  C:\projects
echo =========================================================
cd /d "%~dp0"
python bridge.py --key "D4_PROJECT_MCP_SERVER" --root "C:\projects"
pause
