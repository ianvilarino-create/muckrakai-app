import webview
import subprocess
import threading
import time
import sys
import os

def run_streamlit():
    """Ejecuta el servidor de Streamlit en segundo plano sin abrir pestañas en el navegador web."""
    env = os.environ.copy()
    # Le decimos a Streamlit que no abra el navegador por defecto
    env["STREAMLIT_SERVER_HEADLESS"] = "true" 
    
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "app.py"],
        env=env,
        cwd=directorio_actual
    )

if __name__ == '__main__':
    # Lanzar el servidor en un hilo secundario
    t = threading.Thread(target=run_streamlit, daemon=True)
    t.start()
    
    # Damos tiempo (3 segundos) al servidor de Streamlit para que levante antes de mostrar la ventana
    time.sleep(3)
    
    # Crear y abrir la ventana nativa de escritorio
    webview.create_window(
        'Buscador de Contratos (PCSP) - Auditoría', 
        'http://localhost:8501', 
        width=1366, 
        height=768
    )
    webview.start()
