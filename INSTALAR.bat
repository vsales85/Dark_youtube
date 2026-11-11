@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   DARK STUDIO - instalacao (Windows)
echo ============================================
echo.
where python >nul 2>nul
if errorlevel 1 (
  echo [!] Python nao encontrado. Instale o Python 3.12 em https://www.python.org/downloads/
  echo     e marque "Add python.exe to PATH" na instalacao. Depois rode este arquivo de novo.
  pause & exit /b 1
)
echo [1/4] Ambiente Python isolado (.venv)...
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul

echo.
echo [2/4] Qual placa de video este PC tem?
echo    1 = NVIDIA (GeForce/RTX)
echo    2 = AMD Radeon (Windows, ROCm)
echo    3 = Nenhuma / nao sei  (so os videos de MAPA e voz - funciona em qualquer PC)
set /p PLACA="Digite 1, 2 ou 3: "
if "%PLACA%"=="1" pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
if "%PLACA%"=="2" (
  echo     Para AMD no Windows, instale o PyTorch ROCm seguindo:
  echo     https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html
  echo     e depois rode este instalador de novo escolhendo 3.
)
if "%PLACA%"=="3" pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

echo.
echo [3/4] Bibliotecas do app...
pip install -r requirements.txt
if errorlevel 1 ( echo [!] Falha ao instalar as bibliotecas. & pause & exit /b 1 )

echo.
echo [4/4] Mapas, fontes e dados livres (~400 MB, so na primeira vez)...
python baixar_dados.py
if not exist .env (
  copy .env.example .env >nul
  echo.
  echo [!] Abra o arquivo .env e coloque sua GEMINI_API_KEY (https://aistudio.google.com/apikey)
)
echo.
echo Pronto! Para abrir o painel: ABRIR_PAINEL.bat
pause
