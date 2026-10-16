@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在啟動 PHP 網頁與 Python 解題服務...
"C:\Users\USER\AppData\Local\Programs\Python\Python39\python.exe" "%~dp0run.py"
pause
