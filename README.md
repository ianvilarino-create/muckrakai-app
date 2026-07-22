# MuckrakAI — Buscador y Auditor de Contratos Públicos

## Descripción del Propósito
Esta aplicación web automatiza la detección de anomalías e irregularidades (Red Flags) en contratos reales de la Plataforma de Contratación del Sector Público (PCSP) de España. Está diseñada como una herramienta de apoyo metodológico y tecnológico para periodistas de investigación, permitiendo procesar grandes volúmenes de licitaciones recientes y detectar patrones sospechosos como fraccionamientos de contratos, únicos postores o pliegos restrictivos.

## Plataforma y Tecnologías
- **Plataforma:** Aplicación web *responsive* y multisistema.
- **Lenguaje:** Python 3.14.
- **Framework de Interfaz:** Streamlit.
- **Extracción de Datos y Minería de Texto:** Uso de `requests` y `xml.etree.ElementTree` para la ingesta del Feed Atom oficial del Estado Español. Implementación de técnicas de *Text Mining* y Expresiones Regulares (`re`) para la extracción dinámica de metadatos geográficos y temporales en licitaciones carentes de estructura XML estandarizada.
- **Análisis de Datos:** Pandas.
- **IA y Procesamiento de Lenguaje Natural (NLP):** Integración de `spaCy` (modelo en español) para el análisis semántico de pliegos, memorias justificativas y objetos de contrato.
- **Desarrollo Asistido:** Código estructurado con el apoyo de agentes de Inteligencia Artificial integrados en el entorno de desarrollo.

## Instrucciones de Ejecución Local
1. Clona o descarga este repositorio en tu equipo.
2. Abre una terminal en la carpeta del proyecto.
3. Activa un entorno virtual (recomendado).
4. Instala las dependencias necesarias ejecutando:
   `pip install -r requirements.txt`
5. Descarga el modelo de lenguaje en español para el motor de IA (NLP):
   `python -m spacy download es_core_news_sm`
6. Arranca la aplicación con el comando:
   `python launcher.py` (o en su defecto `streamlit run app.py`)
7. La aplicación se abrirá automáticamente en tu navegador web en `http://localhost:8501`. 
*Nota: La primera ejecución puede tardar unos segundos adicionales mientras el sistema descarga e indexa los datos reales de los últimos 15 días desde los servidores oficiales.*

### macOS: aviso de Gatekeeper al abrir `iniciar_mac.command`

Al descargar el repositorio, macOS marca los archivos como "descargados de Internet" (cuarentena) y bloquea su ejecución con un aviso de este tipo:

> "Apple no ha podido verificar que iniciar_mac.command no contenga software malicioso..."

Esto ocurre con cualquier script descargado, no es un problema del programa. Para solucionarlo, elige una opción:

- **Opción A (recomendada):** clic derecho sobre `iniciar_mac.command` → *Abrir* → confirmar en el diálogo.
- **Opción B:** ve a *Configuración del Sistema → Privacidad y Seguridad* y pulsa *"Abrir de todos modos"* junto al aviso del archivo bloqueado.
- **Opción C (Terminal):** ejecuta una vez

  ```bash
  xattr -d com.apple.quarantine iniciar_mac.command
  ```

  y después ya podrás abrirlo con doble clic con normalidad.

## Autoría
**Ian Vilariño Vicente**

**Tutor:** [Alberto Quian](https://albertoquian.github.io/)

Grao en Xornalismo 

Proxecto da materia Xornalismo Automatizado Intelixente 

Facultade de Ciencias da Comunicación - Universidade de Santiago de Compostela 

Curso 2025-2026 | [ia.xornalismo.gal](https://ia.xornalismo.gal/)