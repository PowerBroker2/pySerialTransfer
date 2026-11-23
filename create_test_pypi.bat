@echo off
python "%~dp0tools\release.py" --repository testpypi
exit /b %errorlevel%
