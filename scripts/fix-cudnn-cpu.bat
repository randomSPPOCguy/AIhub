@echo off
echo ========================================
echo   Quick Fix: Switch to CPU Inference
echo ========================================
echo.
echo This will uninstall onnxruntime-gpu and
echo install onnxruntime (CPU version)
echo.
pause

cd /d "%~dp0..\python_ai"

echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Uninstalling GPU version...
pip uninstall onnxruntime-gpu -y

echo.
echo Installing CPU version...
pip install onnxruntime==1.18.0 onnxruntime-genai

echo.
echo ========================================
echo   Done! Restart AI Hub to use CPU mode
echo ========================================
echo.
echo Note: This will be slower than GPU but
echo      will work without cuDNN.
echo.
echo To use GPU later, install cuDNN and run:
echo   npm run check-cuda
echo.
pause
