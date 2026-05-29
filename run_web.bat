@echo off
set PYTHON_PATH=C:\Users\YQR\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe
if not exist "%PYTHON_PATH%" (
    echo Python not found at: %PYTHON_PATH%
    echo Trying system python...
    set PYTHON_PATH=python
)
cd /d "%~dp0"
"%PYTHON_PATH%" -m streamlit run app.py
pause
