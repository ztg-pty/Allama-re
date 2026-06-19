@echo off
rem download-runtimes.bat
rem Download llama.cpp and CUDA runtime files to RunTime directory

setlocal

set "repoDir=%~dp0"
set "runTimeDir=%repoDir%RunTime"

if not exist "%runTimeDir%" (
    mkdir "%runTimeDir%"
    echo [OK] Created RunTime directory: %runTimeDir%
) else (
    echo [OK] RunTime directory already exists
)

echo ==========================================
echo llama.cpp Runtime Download Script
echo ==========================================
echo.

set "llamaUrl=https://github.com/ggml-org/llama.cpp/releases/download/b9718/llama-b9718-bin-win-cuda-13.3-x64.zip"
set "cudartUrl=https://github.com/ggml-org/llama.cpp/releases/download/b9718/cudart-llama-bin-win-cuda-13.3-x64.zip"

echo Open the following URLs in your browser and download the files:
echo.
echo Save location: %runTimeDir%
echo.
echo [1/2] llama.cpp (152MB)
echo   %llamaUrl%
echo.
echo [2/2] CUDA runtime (373MB)
echo   %cudartUrl%
echo.
echo ------------------------------------------
echo Opening browser...
echo.

start "" "%llamaUrl%"
timeout /t 1 /nobreak >nul
start "" "%cudartUrl%"

echo [OK] Two browser tabs have been opened
echo.
echo ==========================================
echo After downloading, extract the zip files:
echo.
echo   llama.cpp zip: extract .dll / .exe / .bat to RunTime
echo   CUDA zip:      extract cudart*.dll to RunTime
echo.
echo Target directory: %runTimeDir%
echo ==========================================
echo.
pause
