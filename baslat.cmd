@echo off
rem tr2en - deneme baslaticisi (konsollu). Kapatmak icin bu pencerede Ctrl+C.
cd /d "%~dp0"
uv run --extra uygulama --extra yerel tr2en-konsol
pause
