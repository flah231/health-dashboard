@echo off
chcp 65001 >nul
echo ============================================
echo  构建 PyInstaller exe（backend + run_sync）
echo ============================================

cd /d %~dp0

echo.
echo [1/3] 清理旧构建...
rmdir /s /q build\dist 2>nul
rmdir /s /q build\build 2>nul

echo.
echo [2/3] 打包 backend.exe...
cd build
pyinstaller --clean --noconfirm backend.spec
if errorlevel 1 ( echo ❌ backend 打包失败 & exit /b 1 )
cd ..

echo.
echo [3/3] 打包 run_sync.exe...
cd build
pyinstaller --clean --noconfirm collector.spec
if errorlevel 1 ( echo ❌ collector 打包失败 & exit /b 1 )
cd ..

echo.
echo ✅ 打包完成！
echo    backend:   build\dist\backend.exe
echo    run_sync:  build\dist\run_sync.exe
dir build\dist\*.exe