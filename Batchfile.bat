@echo off
REM Runs the warehouse pipeline: full, one stage, or helpers.
REM Usage: Batchfile [full ^| no-extract ^| stage ^| test ^| gx ^| gx-build ^| lint ^| help]
setlocal
set ROOT=%~dp0
set PY=%ROOT%.venv\Scripts\python.exe

if "%~1"=="" goto full
if /I "%~1"=="help" goto help
if /I "%~1"=="full" goto full
if /I "%~1"=="no-extract" goto noextract
if /I "%~1"=="test" goto test
if /I "%~1"=="gx" goto gx
if /I "%~1"=="gx-build" goto gxbuild
if /I "%~1"=="lint" goto lint
goto stage

:full
"%PY%" "%ROOT%main.py"
goto end

:noextract
"%PY%" "%ROOT%main.py" --skip extract
goto end

:test
"%PY%" "%ROOT%scripts\run_all_tests.py"
goto end

:gx
"%PY%" "%ROOT%scripts\run_gx_validations.py"
goto end

:gxbuild
"%PY%" "%ROOT%scripts\setup_gx_project.py"
goto end

:lint
"%PY%" -m ruff check "%ROOT%main.py" "%ROOT%scripts" "%ROOT%tests"
goto end

:stage
"%PY%" "%ROOT%main.py" --only %~1
goto end

:help
echo full                 full extract-to-master run
echo no-extract           full run without Spark extracts
echo extract source-tests staging staging-tests warehouse warehouse-tests analytics analytics-tests master
echo                      run one pipeline stage
echo test                 unit + smoke + dq + gx suites
echo gx                   run all GX layer and master gates
echo gx-build             rebuild GX project from specs
echo lint                 ruff check
goto end

:end
endlocal
