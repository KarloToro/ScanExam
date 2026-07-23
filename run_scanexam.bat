@echo off
:: chcp 65001 cambia a UTF-8 para que las tildes se vean correctamente
chcp 65001 >nul
title ScanExam AI - Corrección automática de exámenes con IA

echo ===================================================
echo             ScanExam AI - Quick Start
echo ===================================================
echo.
echo Este script prepara tu computadora para ejecutar ScanExam AI,
echo una herramienta diseñada para docentes que desean corregir
echo exámenes de opción múltiple de manera rápida y confiable,
echo utilizando solo fotos de fichas tomadas con su celular 
echo a partir de las cuales el sistema genera un excel con
echo los exámenes calificados en cuestión de segundos.
echo.
echo El proceso es seguro y transparente: solo instala las
echo dependencias necesarias y abre la aplicación en tu navegador.
echo ===================================================
echo.

:: -----------------------------------------------------
:: PASO 1: Verificar si 'uv' ya está instalado
:: 'uv' es un gestor de paquetes de Python desarrollado por Astral,
:: empresa adquirida por OpenAI, líder en herramientas para desarrolladores Python.
:: Su función es instalar las librerías necesarias para ScanExam AI.
:: -----------------------------------------------------
where uv >nul 2>nul
if %errorlevel% equ 0 goto RUN_FLOW

:: -----------------------------------------------------
:: PASO 2: Buscar 'uv' en rutas locales de Windows
:: -----------------------------------------------------
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
where uv >nul 2>nul
if %errorlevel% equ 0 goto RUN_FLOW

:: -----------------------------------------------------
:: PASO 3: Descargar 'uv' desde el sitio oficial de Astral
:: -----------------------------------------------------
echo [*] Preparando el entorno por primera vez...
echo [*] Descargando 'uv' desde astral.sh (sitio oficial).
echo    Esto solo ocurrirá una vez y garantiza que las dependencias
echo    se instalen de manera segura y eficiente.
echo.

powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
where uv >nul 2>nul
if %errorlevel% equ 0 goto RUN_FLOW

echo [*] Intentando método alternativo de instalación...
python -m pip install uv >nul 2>nul

where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [AVISO] No se pudo instalar 'uv'.
    echo Por favor, verifica tu conexión a internet e intenta nuevamente.
    echo Si el problema persiste, descarga manualmente 'uv' desde la web oficial.
    echo.
    pause
    exit /b 1
)

:RUN_FLOW
:: -----------------------------------------------------
:: PASO 4: Instalar las librerías necesarias para ScanExam AI
:: - OpenCV: Para analizar las imágenes de las fichas ópticas.
:: - PyTorch: Para clasificar las marcas en las burbujas.
:: - Pandas: Para generar el informe de notas en formato Excel.
:: - NumPy: Para operaciones matemáticas rápidas en memoria.
:: -----------------------------------------------------
echo ===================================================
echo Preparando las librerías de ScanExam AI...
echo ===================================================
echo.

call uv sync
if %errorlevel% neq 0 (
    echo.
    echo [AVISO] Hubo un problema al instalar las librerías.
    echo No te preocupes, esto puede ocurrir por falta de conexión.
    echo Verifica tu internet e intenta de nuevo.
    echo.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo ¡Listo! ScanExam AI se abrirá en tu navegador.
echo ===================================================
echo.
echo ScanExam AI utiliza tecnología de visión por computadora
echo para analizar las fotos de las fichas ópticas.
echo El sistema es seguro, local y no envía tus datos a la nube.
echo.
echo Si tienes dudas, recuerda que 'uv' es una herramienta
echo confiable de Astral, y las librerías principales 
echo son en su mayoría el estándar de facto en el mundo del
echo desarrollo de software con componentes de inteligencia artificial.
echo.

:: -----------------------------------------------------
:: PASO 5: Iniciar el servidor y abrir el navegador
:: -----------------------------------------------------
start http://127.0.0.1:8000

uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload

pause