@echo off

set ARG=%1

if "%ARG%"=="" (
    echo Starting FastAPI server == development
    uvicorn app.main:app --reload --reload-dir ./app --host 127.0.0.1 --port 8000
    @REM gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
    goto :eof
)