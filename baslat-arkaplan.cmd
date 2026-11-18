@echo off
rem tr2en - konsolsuz arkaplan baslaticisi. Pencere hemen kapanir.
cd /d "%~dp0"
uv sync --extra uygulama --extra yerel -q
start "" ".venv\Scripts\pythonw.exe" -m ceviri_katmani.uygulama
