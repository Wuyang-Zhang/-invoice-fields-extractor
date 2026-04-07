@echo off
setlocal
cd /d "%~dp0"

where pyw >nul 2>nul
if %errorlevel%==0 (
    pyw -3 invoice_gui.pyw
    goto :eof
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    pythonw invoice_gui.pyw
    goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
    python invoice_gui.pyw
    goto :eof
)

echo Python was not found in PATH.
pause
