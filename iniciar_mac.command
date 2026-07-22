#!/bin/bash
cd "$(dirname "$0")"
echo "🕵️ Iniciando MuckrakAI..."
echo "   Sistema: macOS"
python3 -m pip install -q -r requirements.txt 2>/dev/null
python3 -m spacy download es_core_news_sm 2>/dev/null
streamlit run app.py
