# =============================================================================
# Archivo: app.py
# Autor: Ian Vilariño Vicente
# Fecha: 29 de mayo de 2026
# Qué hace: Punto de entrada principal y configuración de la interfaz gráfica de Streamlit.
# Licencia: MIT
# =============================================================================

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import os
import warnings
from extractor_pcsp import extraer_datos_reales
from auditoria_alertas import auditar_contratos

warnings.filterwarnings("ignore", category=UserWarning)

# ─── Formato de números en español ──────────────────────────────────────────
def fmt_es(num, decimales=0):
    if pd.isna(num) or num is None: return "—"
    try: num = float(num)
    except (ValueError, TypeError): return str(num)
    if decimales == 0: return f"{int(round(num)):,}".replace(",", ".")
    parte_entera = int(num)
    parte_decimal = f"{abs(num - parte_entera):.{decimales}f}".split(".")[1]
    return f"{parte_entera:,}".replace(",", ".") + "," + parte_decimal

def fmt_eur(num): return fmt_es(num, decimales=2) + " €"

# ─── Configuración ───────────────────────────────────────────────────────────
st.set_page_config(page_title="MuckrakAI — Auditoría de Contratos Públicos", layout="wide", page_icon="🕵️")
st.title("🕵️ MuckrakAI — Buscador y Auditor de Contratos Públicos (NLP & Red Flags)")
st.markdown("Plataforma avanzada para la detección automática de irregularidades en licitaciones y contratos públicos.")

# ─── Indicador de actualización ─────────────────────────────────────────────
cache_path = "contratos_reales_temp.csv"
if os.path.exists(cache_path):
    edad = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))
    horas = int(edad.total_seconds() / 3600)
    mins = int((edad.total_seconds() % 3600) / 60)
    if horas > 0: st.caption(f"🕐 Datos actualizados hace {horas}h {mins}min · Fuente: PCSP")
    else: st.caption(f"🕐 Datos actualizados hace {mins}min · Fuente: PCSP")

# --- CARGA Y ANÁLISIS DE DATOS ---
@st.cache_data(ttl=0)
def load_and_audit_data_v2():
    df_raw = extraer_datos_reales(dias=15)
    if df_raw.empty:
        st.error("No se han podido extraer datos reales de la PCSP. Revisa la conexión o intenta más tarde.")
        return pd.DataFrame()
        # Compatibilidad con versiones anteriores del extractor
    if 'Categoria' in df_raw.columns:
        df_raw = df_raw.rename(columns={"Categoria": "Categoría"})
    if 'Ubicacion' in df_raw.columns:
        df_raw = df_raw.rename(columns={"Ubicacion": "Ubicación"})
    
    # Normalizar nombres de categoría
    if 'Categoría' in df_raw.columns:
        df_raw['Categoría'] = df_raw['Categoría'].replace({
            "Suministros": "Suministros Generales",
            "Suministros de TI": "Suministros Tecnológicos (TI)"
        })
    
    df_audited = auditar_contratos(df_raw)
    return df_audited

df = load_and_audit_data_v2()

if df.empty:
    st.stop()

# Forzar la columna a tipo texto plano y recortar estrictamente los primeros 10 caracteres (YYYY-MM-DD)
if 'Fecha Adjudicación' in df.columns:
    df['Fecha Adjudicación'] = df['Fecha Adjudicación'].astype(str).str.slice(0, 10)
elif 'Fecha Adjudicacion' in df.columns:  # Soporte para nombre original de la columna sin tilde
    df['Fecha Adjudicacion'] = df['Fecha Adjudicacion'].astype(str).str.slice(0, 10)

# ─── Sidebar: Filtros ───────────────────────────────────────────────────────
st.sidebar.header("🔍 Filtros de Búsqueda")
search_text = st.sidebar.text_input("Buscar texto (Objeto, Adjudicatario, Expediente)")

# Filtro por rango de importe
col_min, col_max = st.sidebar.columns(2)
with col_min:
    importe_min = st.number_input("Importe mín (€)", value=0, step=1000, format="%d")
with col_max:
    importe_max = st.number_input("Importe máx (€)", value=0, step=1000, format="%d")
    if importe_max == 0: importe_max = int(df['Importe'].max()) + 1

# Filtro por rango de fechas (usa Fecha Adjudicacion que tiene fechas reales distribuidas)
if 'Fecha Adjudicacion' in df.columns:
    df['_fecha_dt'] = pd.to_datetime(df['Fecha Adjudicacion'], errors='coerce')
    fechas_validas = df['_fecha_dt'].dropna()
    if len(fechas_validas) > 0:
        min_date = fechas_validas.min().date()
        max_date = fechas_validas.max().date()
    else:
        min_date = datetime.now().date() - timedelta(days=15)
        max_date = datetime.now().date()
    st.sidebar.caption("Filtro por fecha de adjudicación (solo contratos ya resueltos)")
    fecha_range = st.sidebar.date_input("Rango fecha adjudicación", value=(min_date, max_date), min_value=min_date, max_value=max_date)

cat_opts = sorted(df['Categoría'].dropna().unique().tolist())
filtro_categorias = st.sidebar.multiselect("Categorías", cat_opts, default=[], key="filtro_cat")
ubicacion_opts = sorted(df['Ubicación'].dropna().unique().tolist())
filtro_ubicaciones = st.sidebar.multiselect("Ubicación", ubicacion_opts, default=[], key="filtro_ubi")
filtro_red_flags = st.sidebar.slider("Mínimo de Alertas (Red Flags)", min_value=0, max_value=int(df['Num Red Flags'].max()) if len(df)>0 else 5, value=0)
proc_opts = ["Todos los procedimientos"] + sorted(df['Procedimiento'].dropna().unique().tolist())
filtro_proc = st.sidebar.selectbox("Procedimiento", proc_opts)

# Export Excel
st.sidebar.markdown("---")
st.sidebar.caption("💾 Exportar datos filtrados")
@st.cache_data
def to_excel(df_to_export):
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_to_export.to_excel(writer, index=False, sheet_name='Contratos')
    return output.getvalue()

st.sidebar.markdown("---")
st.sidebar.markdown("""
**MuckrakAI**

**Autor:** Ian Vilariño Vicente

**Tutor:** [Alberto Quian](https://albertoquian.github.io/)

**Traballo de Fin de Grao**

Facultade de CC. da Comunicación — USC

Curso 2025-2026 | [ia.xornalismo.gal](https://ia.xornalismo.gal/)
""")

# Aplicar filtros
df_filtrado = df.copy()
if filtro_categorias: df_filtrado = df_filtrado[df_filtrado['Categoría'].isin(filtro_categorias)]
if filtro_ubicaciones: df_filtrado = df_filtrado[df_filtrado['Ubicación'].isin(filtro_ubicaciones)]
if search_text:
    mask = (df_filtrado['Objeto'].str.contains(search_text, case=False, na=False) | df_filtrado['Adjudicatario'].str.contains(search_text, case=False, na=False) | df_filtrado['ID_Expediente'].str.contains(search_text, case=False, na=False))
    df_filtrado = df_filtrado[mask]
if filtro_red_flags > 0: df_filtrado = df_filtrado[df_filtrado['Num Red Flags'] >= filtro_red_flags]
if filtro_proc != "Todos los procedimientos": df_filtrado = df_filtrado[df_filtrado['Procedimiento'] == filtro_proc]
if importe_min > 0 or importe_max < df['Importe'].max():
    df_filtrado = df_filtrado[(df_filtrado['Importe'] >= importe_min) & (df_filtrado['Importe'] <= importe_max)]
if 'Fecha Adjudicacion' in df.columns and '_fecha_dt' in df.columns:
    try:
        if fecha_range is not None and len(fecha_range) == 2:
            f0 = pd.to_datetime(fecha_range[0])
            f1 = pd.to_datetime(fecha_range[1]) + timedelta(days=1)
            mask_fecha = (df_filtrado['_fecha_dt'] >= f0) & (df_filtrado['_fecha_dt'] < f1)
            df_filtrado = df_filtrado[mask_fecha]
    except (NameError, TypeError, ValueError):
        pass

excel_data = to_excel(df_filtrado)
st.sidebar.download_button("📥 Descargar Excel", data=excel_data, file_name="contratos_pcsp.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ─── Helpers ─────────────────────────────────────────────────────────────────
def format_alertas(alertas_list):
    if not alertas_list: return "✅ OK"
    return " | ".join([f"🔴 {x[0]}: {x[1]}" for x in alertas_list])

def enlace_pcsp(id_exp):
    """Ya no se usa — las URLs vienen del feed Atom directamente."""
    return f"https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl={id_exp}"

df_filtrado['Agrupación Alertas'] = df_filtrado['Red Flags'].apply(format_alertas)

# ═══════════════════════════════════════════════════════════════════════════════
# PESTAÑAS
# ═══════════════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["📊 Explorador de Contratos", "🚨 Auditoría de Anomalías"])

# ─── PESTAÑA 1: EXPLORADOR ──────────────────────────────────────────────────
with tab1:
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Contratos", fmt_es(len(df_filtrado)))
    importe_total = df_filtrado['Importe'].sum()
    importe_promedio = df_filtrado['Importe'].mean() if len(df_filtrado) > 0 else 0
    col2.metric("Importe Total", fmt_eur(importe_total))
    col3.metric("Importe Promedio", fmt_eur(importe_promedio))
    adjudicados = (df_filtrado['Adjudicatario'] != 'No adjudicado aún').sum()
    col4.metric("Adjudicados", f"{adjudicados} ({adjudicados/max(1,len(df_filtrado))*100:.0f}%)")

    # ── Fila 1: Distribución por categoría y procedimiento ──────────────────
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.subheader("📈 Distribución por Categoría")
        cat_counts = df_filtrado['Categoría'].value_counts().reset_index()
        cat_counts.columns = ['Categoría', 'Contratos']
        chart_cat = alt.Chart(cat_counts).mark_bar().encode(
            x=alt.X('Contratos:Q', title='Nº de contratos'),
            y=alt.Y('Categoría:N', title=None, sort='-x'),
            color=alt.Color('Categoría:N', legend=None)
        ).properties(height=150)
        st.altair_chart(chart_cat, use_container_width=True)

    with chart_col2:
        st.subheader("📈 Distribución por Procedimiento")
        proc_counts = df_filtrado['Procedimiento'].value_counts().reset_index()
        proc_counts.columns = ['Procedimiento', 'Contratos']
        chart_proc = alt.Chart(proc_counts).mark_bar().encode(
            x=alt.X('Contratos:Q', title='Nº de contratos'),
            y=alt.Y('Procedimiento:N', title=None, sort='-x'),
            color=alt.Color('Procedimiento:N', legend=None)
        ).properties(height=150)
        st.altair_chart(chart_proc, use_container_width=True)

    # ── Fila 2: Top adjudicatarios + Top ubicaciones ────────────────────────
    chart_col3, chart_col4 = st.columns(2)
    with chart_col3:
        st.subheader("🏢 Top 10 Adjudicatarios por Importe")
        top_adj = df_filtrado[df_filtrado['Adjudicatario'] != 'No adjudicado aún'].groupby('Adjudicatario')['Importe'].sum().nlargest(10).reset_index()
        top_adj.columns = ['Adjudicatario', 'Importe Total']
        top_adj['Adjudicatario'] = top_adj['Adjudicatario'].str[:40]
        chart_adj = alt.Chart(top_adj).mark_bar().encode(
            x=alt.X('Importe Total:Q', title='Importe acumulado (€)'),
            y=alt.Y('Adjudicatario:N', title=None, sort='-x'),
            color=alt.Color('Importe Total:Q', legend=None, scale=alt.Scale(scheme='blues'))
        ).properties(height=200)
        st.altair_chart(chart_adj, use_container_width=True)

    with chart_col4:
        st.subheader("📍 Contratos por Ubicación (Top 15)")
        loc_counts = df_filtrado['Ubicación'].value_counts().nlargest(15).reset_index()
        loc_counts.columns = ['Ubicación', 'Contratos']
        chart_loc = alt.Chart(loc_counts).mark_bar().encode(
            x=alt.X('Contratos:Q', title='Nº de contratos'),
            y=alt.Y('Ubicación:N', title=None, sort='-x'),
            color=alt.Color('Contratos:Q', legend=None, scale=alt.Scale(scheme='reds'))
        ).properties(height=200)
        st.altair_chart(chart_loc, use_container_width=True)

    # ── Fila 3: Histograma de importes ─────────────────────────────────────
    st.subheader("💰 Distribución de Importes")
    hist = alt.Chart(df_filtrado).mark_bar().encode(
        alt.X('Importe:Q', bin=alt.Bin(maxbins=40), title='Importe (€)'),
        alt.Y('count():Q', title='Nº de contratos'),
        color=alt.value('#1f77b4')
    ).properties(height=150)
    st.altair_chart(hist, use_container_width=True)

    # ── Tabla explorador ──────────────────────────────────────────────────
    st.subheader("📋 Datos Técnicos Generales")
    cols_explorador = ['ID_Expediente', 'Objeto', 'Categoría', 'Ubicación', 'Estado', 'Importe', 'Fecha Adjudicacion', 'Organo Contratacion', 'Adjudicatario', 'Num Ofertas']
    cols_con_url = cols_explorador + (['URL Licitacion'] if 'URL Licitacion' in df_filtrado.columns else [])
    df_explorador = df_filtrado[cols_con_url].copy()
    df_explorador = df_explorador.rename(columns={'Fecha Adjudicacion': 'Fecha Adjudicación', 'Num Ofertas': 'Nº Ofertas'})
    if 'Objeto' in df_explorador.columns:
        df_explorador['Objeto'] = df_explorador['Objeto'].apply(lambda x: str(x)[:100] + '…' if len(str(x)) > 100 else str(x))
    if 'Fecha Adjudicación' in df_explorador.columns:
        df_explorador['Fecha Adjudicación'] = df_explorador['Fecha Adjudicación'].astype(str).replace({'NaT': 'Pendiente', 'nan': 'Pendiente', 'None': 'Pendiente', '': 'Pendiente'})
    if 'Ubicación' in df_explorador.columns:
        df_explorador['Ubicación'] = df_explorador['Ubicación'].str.replace('/valència', '', regex=False).str.replace('/alacant', '', regex=False)

    # Guardar mapa de URLs para el selector rápido
    urls_map = {}
    if 'URL Licitacion' in df_explorador.columns:
        for i, row in df_explorador.iterrows():
            u = row['URL Licitacion']
            if pd.notna(u) and str(u) != '':
                urls_map[row['ID_Expediente']] = str(u)
        df_explorador = df_explorador.drop(columns=['URL Licitacion'])

    # Selector rápido para abrir expediente en PCSP
    with st.container():
        col_a, col_b = st.columns([3, 1])
        with col_a:
            exp_sel = st.selectbox("🔗 Ir a expediente en la PCSP:", options=[""] + list(urls_map.keys()), key="exp_sel", label_visibility="collapsed", placeholder="Escribe o selecciona un ID de expediente…")
        with col_b:
            if exp_sel and exp_sel in urls_map:
                st.link_button("🔗 Abrir en PCSP", url=urls_map[exp_sel], type="primary")

    st.dataframe(df_explorador, width='stretch', hide_index=True)

# ─── PESTAÑA 2: AUDITORÍA ────────────────────────────────────────────────────
with tab2:
    st.subheader("Periodismo de Investigación: Detección de Riesgos")

    # ── Panel resumen de Red Flags ────────────────────────────────────────
    st.markdown("### 📊 Resumen de Anomalías Detectadas")
    total_alertas = df_filtrado['Num Red Flags'].sum()
    contratos_con_alertas = (df_filtrado['Num Red Flags'] > 0).sum()

    todos_los_flags = []
    for alertas in df_filtrado['Red Flags']:
        for a in alertas: todos_los_flags.append(a[0])
    flags_series = pd.Series(todos_los_flags)

    res_col1, res_col2, res_col3 = st.columns(3)
    with res_col1: st.metric("Total Alertas", fmt_es(total_alertas))
    with res_col2:
        pct = contratos_con_alertas / max(1, len(df_filtrado)) * 100
        st.metric("Contratos con Alertas", f"{fmt_es(contratos_con_alertas)} ({pct:.0f}%)")
    with res_col3:
        alto_riesgo = (df_filtrado['Num Red Flags'] >= 3).sum()
        st.metric("Alto Riesgo (≥3 flags)", fmt_es(alto_riesgo))

    # Top tipos de alerta
    if len(flags_series) > 0:
        st.markdown("#### 🔝 Tipos de Alerta más Frecuentes")
        top_flags = flags_series.value_counts().head(5)
        cols_f = st.columns(len(top_flags))
        for i, (codigo, count) in enumerate(top_flags.items()):
            with cols_f[i]: st.metric(codigo, fmt_es(count))

        # Top órganos con más alertas
        st.markdown("#### 🏛️ Órganos con más Alertas")
        organos_alertas = df_filtrado.groupby('Organo Contratacion')['Num Red Flags'].sum().nlargest(5).reset_index()
        organos_alertas.columns = ['Órgano', 'Alertas']
        chart_org = alt.Chart(organos_alertas).mark_bar().encode(
            y=alt.Y('Órgano:N', title=None, sort='-x'),
            x=alt.X('Alertas:Q', title='Nº total de alertas'),
            color=alt.value('#e74c3c')
        ).properties(height=120)
        st.altair_chart(chart_org, use_container_width=True)

    st.markdown("---")

    # ── Filtro por tipología ──────────────────────────────────────────────
    lista_alertas_estaticas = [
        "Todas las anomalías",
        "F01: Contrato menor en límite legal",
        "F02: Riesgo de fraccionamiento o carrusel",
        "F03: Objeto del contrato excesivamente genérico",
        "F04: Plazo de ejecución sospechosamente corto",
        "F05: Posible mención a marca/patente",
        "F06: Baja temeraria detectada",
        "F07: Único postor en procedimiento abierto",
        "F12: Retraso de inicio > 3 meses desde adjudicación",
    ]
    st.caption("⚠️ F08-F11 y F13 requieren datos externos no disponibles en el feed Atom (registro mercantil, modificaciones, prórrogas, pagos).")

    alerta_seleccionada = st.selectbox("Filtrar por Tipología de Anomalía (Red Flag)", lista_alertas_estaticas)
    df_anomalias = df_filtrado.copy()
    if alerta_seleccionada != "Todas las anomalías":
        seleccion_base = alerta_seleccionada.split(":")[0]
        df_anomalias = df_anomalias[df_anomalias['Agrupación Alertas'].str.contains(seleccion_base, case=False, na=False)]

    cols_riesgo = ['ID_Expediente', 'Adjudicatario', 'Importe', 'Num Red Flags', 'Agrupación Alertas']
    st.dataframe(df_anomalias[cols_riesgo], width='stretch', hide_index=True)

    # ── Detalle del expediente ────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🔎 Detalle del Expediente Sospechoso")
    if len(df_anomalias) > 0:
        expediente_sel = st.selectbox("Seleccione un expediente para investigar a fondo", df_anomalias['ID_Expediente'].tolist())
        if expediente_sel:
            detalle = df_anomalias[df_anomalias['ID_Expediente'] == expediente_sel].iloc[0]
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown(f"**Órgano:** {detalle['Organo Contratacion']}")
                st.markdown(f"**Adjudicatario:** {detalle['Adjudicatario']}")
                st.markdown(f"**Objeto:** {detalle['Objeto']}")
                st.markdown(f"**Procedimiento:** {detalle['Procedimiento']}")
                st.markdown(f"**Importe:** {fmt_eur(detalle['Importe'])} (Presupuesto: {fmt_eur(detalle['Presupuesto Base'])})")
                url_pcsp = detalle.get('URL Licitacion', '')
                if url_pcsp and str(url_pcsp) != '' and str(url_pcsp) != 'nan':
                    st.markdown(f"🔗 [Ver expediente en la PCSP]({url_pcsp})")
            with c2:
                st.markdown("### 🚨 Panel de Riesgo")
                if detalle['Num Red Flags'] == 0:
                    st.success("No se detectaron alertas estructurales ni documentales.")
                else:
                    st.error(f"Se encontraron {detalle['Num Red Flags']} alerta(s)")
                    for a in detalle['Red Flags']:
                        st.warning(f"**{a[0]}**: {a[1]}")
    else:
        st.info("No hay contratos que coincidan con los filtros seleccionados.")

# Trigger reload
