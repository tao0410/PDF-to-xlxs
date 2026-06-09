@echo off
REM PDF信息提取工具 - PyInstaller 打包脚本
REM 使用 .spec 文件以确保所有资源和依赖正确打包
REM 参照 development.md §7

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo ============================================
echo PDF信息提取工具 - PyInstaller 打包
echo ============================================
echo.

REM 清理旧的构建文件
if exist "build\" rmdir /s /q build
if exist "dist\PDF信息提取工具.exe" del /q "dist\PDF信息提取工具.exe"

echo [1/2] 正在打包（使用 .spec 配置文件）...
py -m PyInstaller --clean "PDF信息提取工具.spec"

if exist "dist\PDF信息提取工具.exe" (
    echo.
    echo [2/2] 复制配置文件到 dist 目录...
    copy /Y "default.cfg" "dist\" >nul
    if not exist "dist\resources\" mkdir "dist\resources"
    copy /Y "resources\styles.qss" "dist\resources\" >nul
    echo.
    echo ============================================
    echo  打包完成!
    echo  dist\PDF信息提取工具.exe
    echo ============================================
    echo.
    echo 交付清单（dist 目录）:
    echo   - PDF信息提取工具.exe  （主程序）
    echo   - default.cfg           （默认配置）
    echo   - resources\styles.qss  （样式表）
    echo.
    echo Win7 部署提示:
    echo   1. 确保安装 VC++ 2015-2022 Redistributable
    echo      (vc_redist.x64.exe / vc_redist.x86.exe)
    echo   2. 确保安装 KB2999226 更新（Universal CRT）
    echo   3. 将整个 dist 文件夹复制到目标机器
    echo   4. default.cfg 必须与 exe 在同一目录
) else (
    echo.
    echo 打包失败！
    echo 请检查:
    echo   1. PyInstaller 是否已安装: py -m pip show pyinstaller
    echo   2. 所有依赖是否已安装: py -m pip install -r requirements.txt
    exit /b 1
)
