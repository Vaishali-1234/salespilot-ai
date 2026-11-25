@echo off
title SalesPilot AI Launcher
cd /d "%~dp0"
echo Starting SalesPilot AI FastAPI Backend on http://127.0.0.1:8000 ...
start "SalesPilot Backend (FastAPI)" cmd /k "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"

echo Waiting for FastAPI backend /health to respond...
powershell -NoProfile -Command "for ($i=0; $i -lt 30; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2; if ($r.StatusCode -eq 200) { Write-Host 'Backend is UP!'; exit 0 } } catch {}; Start-Sleep -Seconds 2 }; Write-Host 'Backend still starting; check the FastAPI window for details.'"

echo Launching Streamlit UI on http://localhost:8501 ...
start "SalesPilot Frontend (Streamlit)" cmd /k "python -m streamlit run app.py --server.port 8501"
