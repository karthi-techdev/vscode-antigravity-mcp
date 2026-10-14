@echo off
title Universal IDE Bridge (On-Demand Session)
cd /d "%~dp0"
python -u bridge.py %*
pause
