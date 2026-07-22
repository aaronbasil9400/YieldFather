@echo off
cd /d "%~dp0"

if not exist "logs" mkdir "logs"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%i

powershell -WindowStyle Hidden -Command ^
"Start-Process python -ArgumentList '-m streamlit run Home.py' -RedirectStandardOutput 'logs\launcher_%TS%.log' -RedirectStandardError 'logs\launcher_%TS%.log' -WindowStyle Hidden"

exit