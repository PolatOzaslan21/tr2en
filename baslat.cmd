@echo off
rem Ceviri Katmani - deneme baslaticisi. Kapatmak icin bu pencerede Ctrl+C.
cd /d "%~dp0"
uv run --extra uygulama --extra yerel ceviri-uygulama
pause
