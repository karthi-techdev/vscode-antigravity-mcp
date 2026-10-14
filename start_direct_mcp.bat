@echo off
title Universal IDE Direct FastMCP Server
echo =========================================================
echo Starting Universal IDE Direct MCP Server...
echo Engine: FastMCP + Cloudflare Tunnel (Zero Timeout)
echo Root:   C:\projects
echo =========================================================
cd /d "%~dp0"
python -u direct_mcp.py --root "C:\projects"
pause
