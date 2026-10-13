@echo off
rem PROBE_SYCL.bat: build probe_sycl.cpp with oneAPI and record what the SYCL runtime reports, three ways:
rem   default.json  - no extra switches
rem   sysman.json   - ZES_ENABLE_SYSMAN=1 (the native engine's setup sets it, PR #2079)
rem   relaxed.json  - ZES_ENABLE_SYSMAN=1 and UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 (strata-sycl-native.sh sets it)
rem Read-only: nothing is installed, no system setting is changed. Reports go to reports\sycl-<date>-<time>.
setlocal
cd /d "%~dp0"
where icx >nul 2>nul
if errorlevel 1 (
    if not defined VS2022INSTALLDIR if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\VC" set "VS2022INSTALLDIR=%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools"
    if not defined ONEAPI_ROOT set "ONEAPI_ROOT=%ProgramFiles(x86)%\Intel\oneAPI"
    call "%%ONEAPI_ROOT%%\setvars.bat" intel64 vs2022 >nul
)
where icx >nul 2>nul
if errorlevel 1 (
    echo Intel oneAPI icx was not found. Run oneAPI setvars.bat first.
    exit /b 1
)
where cl >nul 2>nul
if errorlevel 1 (
    echo The Visual Studio C++ tools were not found ^(cl.exe^). Set VS2022INSTALLDIR and run setvars.bat again.
    exit /b 1
)
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%I"
set "OUT=%~dp0reports\sycl-%STAMP%"
mkdir "%OUT%"
icx --version > "%OUT%\icx-version.txt" 2>&1
sycl-ls > "%OUT%\sycl-ls.txt" 2>&1
echo Building probe_sycl.exe ...
icx -fsycl /O2 /EHsc -Wno-deprecated-declarations probe_sycl.cpp /Fo"%OUT%\probe_sycl.obj" /Fe"%OUT%\probe_sycl.exe" > "%OUT%\build.txt" 2>&1
if errorlevel 1 (
    echo Build failed. See "%OUT%\build.txt"
    exit /b 1
)
"%OUT%\probe_sycl.exe" > "%OUT%\default.json" 2> "%OUT%\default-stderr.txt"
echo default: exit %ERRORLEVEL%
set "ZES_ENABLE_SYSMAN=1"
"%OUT%\probe_sycl.exe" > "%OUT%\sysman.json" 2> "%OUT%\sysman-stderr.txt"
echo sysman: exit %ERRORLEVEL%
set "UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1"
"%OUT%\probe_sycl.exe" > "%OUT%\relaxed.json" 2> "%OUT%\relaxed-stderr.txt"
echo relaxed: exit %ERRORLEVEL%
echo.
echo Reports: "%OUT%"
exit /b 0
