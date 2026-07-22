@echo off
cd /d "%~dp0"
echo 🕵️ Iniciando MuckrakAI...
echo    Sistema: Windows
python -m pip install -q -r requirements.txt >nul 2>&1
python -m spacy download es_core_news_sm >nul 2>&1
streamlit run app.py
pause
