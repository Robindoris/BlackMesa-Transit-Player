@echo off
"%~dp0TransitPlayer\runtime\python.exe" "%~dp0TransitPlayer\launcher.py" player
if errorlevel 1 pause
