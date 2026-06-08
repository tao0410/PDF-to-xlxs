@echo off
REM PDF信息提取工具 - PyInstaller 打包脚本
REM 参照 development.md §7

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo 正在打包 PDF信息提取工具 ...
py -m PyInstaller --onefile --windowed --name=PDF信息提取工具 main.py

if exist "dist\PDF信息提取工具.exe" (
    copy /Y default.cfg dist\
    echo.
    echo 打包完成: dist\PDF信息提取工具.exe
    echo 请将 default.cfg 与 exe 放在同一目录下使用。
) else (
    echo 打包失败，请检查 PyInstaller 是否已安装。
    exit /b 1
)
