@echo off
REM Launches VS Code with the MSVC toolchain (cl.exe / nmake.exe) already on
REM PATH -- zenoh-pico's PlatformIO build hook (extra_script.py) needs this
REM to satisfy CMake's native compiler check, even though nothing here
REM actually gets cross-compiled for the ESP32 itself.
REM
REM IMPORTANT: close every VS Code window first (check Task Manager for a
REM leftover Code.exe too). If one is already running, "code" just tells
REM the existing process to open this workspace -- it won't get this
REM script's environment, and you'll be right back to the nmake error.

echo Close all VS Code windows (and check Task Manager for leftover
echo Code.exe processes) before continuing.
pause

call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
if errorlevel 1 (
    echo vcvarsall.bat failed -- confirm Visual Studio Build Tools is still
    echo installed at the path above ^(the install location can change if
    echo Build Tools gets upgraded^).
    pause
    exit /b 1
)

code "%~dp0..\collab_sandbox.code-workspace"
