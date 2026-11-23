@echo off
python "%~dp0tools\release.py" --repository pypi
exit /b %errorlevel%
