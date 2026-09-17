@echo off
cd /d C:\muraai-refer-updated\muraai\backend
"C:\muraai-refer-updated\muraai\backend\venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >> "C:\muraai-refer-updated\muraai\backend\server.out.log" 2>> "C:\muraai-refer-updated\muraai\backend\server.err.log"
