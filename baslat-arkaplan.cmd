@echo off
rem tr2en - konsolsuz arkaplan baslaticisi. Pencere hemen kapanir.
rem .venv\Scripts\tr2en.exe GUI baslaticisidir (uv'nin pythonw.exe'si konsol aciyor).
cd /d "%~dp0"
uv sync --extra uygulama --extra yerel -q
start "" ".venv\Scripts\tr2en.exe"
exit
