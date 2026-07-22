"""
Lanzador cross-platform para el Buscador y Auditor de Contratos Públicos.
Compatible con Windows, macOS y Linux.
Doble clic en el script correspondiente a tu sistema operativo.
"""
import subprocess
import time
import sys
import os
import webbrowser
import platform


def find_python():
    """Busca un intérprete de Python 3 funcional en el sistema."""
    candidates = []
    sistema = platform.system()

    if sistema == "Windows":
        candidates = ["python", "python3", "py", "py -3"]
    else:
        candidates = ["python3", "python"]

    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd.split() + ["--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and "Python 3" in result.stdout + result.stderr:
                return cmd.split()
        except Exception:
            continue
    return None


def check_and_install_deps(python_cmd, cwd):
    """Verifica e instala dependencias si es necesario."""
    print("Verificando dependencias...")
    try:
        subprocess.run(
            python_cmd + ["-c", "import streamlit, pandas, spacy, feedparser, requests, openpyxl, altair"],
            capture_output=True, cwd=cwd, timeout=10
        )
        print("  Dependencias OK.")
        return True
    except subprocess.CalledProcessError:
        print("  Instalando dependencias (esto puede tardar unos minutos)...")
        try:
            subprocess.run(
                python_cmd + ["-m", "pip", "install", "-r", "requirements.txt", "-q"],
                cwd=cwd, check=True
            )
            # Instalar modelo spaCy
            subprocess.run(
                python_cmd + ["-m", "spacy", "download", "es_core_news_sm", "-q"],
                cwd=cwd
            )
            print("  Dependencias instaladas correctamente.")
            return True
        except Exception as e:
            print(f"  Error instalando dependencias: {e}")
            return False


def open_browser(url):
    """Abre el navegador del sistema de forma cross-platform."""
    sistema = platform.system()
    try:
        if sistema == "Darwin":  # macOS
            subprocess.Popen(["open", url])
        elif sistema == "Windows":
            os.startfile(url)
        else:  # Linux y otros
            subprocess.Popen(["xdg-open", url])
    except Exception:
        webbrowser.open(url)


def start_app():
    sistema = platform.system()
    print(f"🕵️ Buscador y Auditor de Contratos Públicos")
    print(f"   Sistema detectado: {sistema}")
    print(f"   Python: {sys.executable}")
    print()

    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    os.chdir(directorio_actual)

    # Verificar dependencias
    if not check_and_install_deps([sys.executable], directorio_actual):
        print("\n❌ No se pudieron instalar las dependencias.")
        print("   Asegúrate de tener Python 3.9+ instalado y conexión a internet.")
        input("Presiona Enter para salir...")
        sys.exit(1)

    # Variables de entorno
    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"

    print("Iniciando servidor de datos...")
    app_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py"],
        env=env,
        cwd=directorio_actual,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Esperar a que Streamlit esté listo
    time.sleep(3)

    url = "http://localhost:8501"
    print(f"Abriendo navegador en {url} ...")
    open_browser(url)

    print("\n✅ App funcionando. No cierres esta ventana mientras uses la aplicación.")
    print("   Para salir, presiona Ctrl+C o cierra esta ventana.")
    print(f"   Si el navegador no se abre, visita manualmente: {url}")

    try:
        app_process.wait()
    except KeyboardInterrupt:
        print("\nCerrando servidor...")
        app_process.terminate()
        app_process.wait()
        print("Servidor cerrado.")


if __name__ == "__main__":
    start_app()
    # Mantener ventana abierta en Windows
    if platform.system() == "Windows":
        input("\nPresiona Enter para cerrar esta ventana...")
