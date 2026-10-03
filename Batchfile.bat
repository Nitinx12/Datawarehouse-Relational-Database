@echo off
REM Runs the warehouse pipeline: full, one stage, or helpers.
REM Usage: Batchfile [full ^| no-extract ^| stage ^| test ^| gx ^| gx-build ^| lint ^| dashboard ^| dashboard-install ^| infra-up ^| infra-down ^| infra-logs ^| airflow-trigger ^| help]
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
if /I "%~1"=="dashboard" goto dashboard
if /I "%~1"=="dashboard-install" goto dashinstall
if /I "%~1"=="infra-up" goto infraup
if /I "%~1"=="infra-down" goto infradown
if /I "%~1"=="infra-logs" goto infralogs
if /I "%~1"=="airflow-trigger" goto airflowtrigger
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
"%PY%" -m ruff check "%ROOT%main.py" "%ROOT%scripts" "%ROOT%tests" "%ROOT%dashboard" "%ROOT%airflow\dags"
goto end

:stage
"%PY%" "%ROOT%main.py" --only %~1
goto end

:dashinstall
uv pip install --python "%PY%" -r "%ROOT%dashboard\requirements.txt"
goto end

:dashboard
"%PY%" -m streamlit run "%ROOT%dashboard\home.py"
goto end

:infraup
cd /d "%ROOT%" && docker compose up -d --build
goto end

:infradown
cd /d "%ROOT%" && docker compose down
goto end

:infralogs
cd /d "%ROOT%" && docker compose logs -f
goto end

:airflowtrigger
cd /d "%ROOT%" && docker compose exec airflow-scheduler airflow dags trigger warehouse_daily
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
echo dashboard-install   install dashboard deps into .venv
echo dashboard            run the Streamlit dashboard
echo infra-up             build + start postgres, mongo, airflow, dashboard
echo infra-down           stop the stack (keeps volumes)
echo infra-logs           follow stack logs
echo airflow-trigger      trigger one warehouse_daily run
goto end

:end
endlocal
