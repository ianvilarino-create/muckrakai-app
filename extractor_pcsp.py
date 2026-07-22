# =============================================================================
# Archivo: extractor_pcsp.py
# Autor: Ian Vilariño Vicente
# Revisión: 2026-07-09 — Extracción multi-página con datos 100% reales
# Qué hace: Conexión al feed Atom de la PCSP con paginación histórica.
# Licencia: MIT
# =============================================================================

import pandas as pd
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
import os
import re
import time

# ─── Namespaces del feed Atom PCSP ───────────────────────────────────────────
NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'cac':  'urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2',
    'cbc':  'urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2',
}

# ─── Mapeos PCSP ─────────────────────────────────────────────────────────────
MAPA_PROCEDIMIENTO = {
    '1': 'Abierto', '2': 'Restringido', '3': 'Negociado',
    '4': 'Diálogo competitivo', '5': 'Asociación para la innovación',
    '6': 'Licitación con negociación', '7': 'Concurso de proyectos',
    '8': 'Abierto simplificado', '9': 'Abierto simplificado abreviado',
    '10': 'Menor', '11': 'Derivado de acuerdo marco',
    '12': 'Sistema dinámico de adquisición', '13': 'Abierto supersimplificado',
}

MAPA_TIPO_CONTRATO = {
    '1': 'Obras', '2': 'Suministros Generales', '3': 'Servicios',
    '4': 'Concesión de Obras', '5': 'Concesión de Servicios',
    '6': 'Suministros Tecnológicos (TI)', '7': 'Mixto',
    '8': 'Administrativo especial', '9': 'Patrimonial',
}

MAPA_ESTADO = {
    'AN': 'Anulado', 'AD': 'Adjudicado', 'AD.PEND': 'Adjudicado pendiente',
    'BO': 'En plazo', 'EV': 'Evaluación', 'RE': 'Resuelto', 'DE': 'Desistido',
}

MAPA_LOCALIDADES = [
    "A CORUÑA", "ALBACETE", "ALICANTE", "ALMERÍA", "ÁLAVA", "ASTURIAS",
    "ÁVILA", "BADAJOZ", "BARCELONA", "BURGOS", "CÁCERES", "CÁDIZ",
    "CANTABRIA", "CASTELLÓN", "CIUDAD REAL", "CÓRDOBA", "CUENCA", "GIRONA",
    "GRANADA", "GUADALAJARA", "HUELVA", "HUESCA", "BALEARES", "JAÉN",
    "LEÓN", "LLEIDA", "LUGO", "MADRID", "MÁLAGA", "MURCIA", "NAVARRA",
    "OURENSE", "PALENCIA", "LAS PALMAS", "PONTEVEDRA", "LA RIOJA",
    "SALAMANCA", "TENERIFE", "SEGOVIA", "SEVILLA", "SORIA", "TARRAGONA",
    "TERUEL", "TOLEDO", "VALENCIA", "VALLADOLID", "ZAMORA", "ZARAGOZA",
    "CEUTA", "MELILLA",
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _text(el):
    return el.text.strip() if el is not None and el.text else None


def _find_first(entry, xpath_candidates):
    for xpath in xpath_candidates:
        el = entry.find(xpath, NS)
        if el is not None and el.text:
            return el.text.strip()
    return None


def _extract_tender_results(entry):
    resultados = entry.findall('.//cac:TenderResult', NS)
    if not resultados:
        return None, None, None, None

    tr = resultados[0]
    adjudicatario = _find_first(tr, [
        'cac:WinningParty/cac:PartyName/cbc:Name',
        'cac:WinningParty/cac:PartyLegalEntity/cbc:CompanyID',
        'cac:WinningParty/cbc:CompanyID',
    ])
    if adjudicatario:
        adjudicatario = adjudicatario.strip().rstrip(',')

    num_ofertas = _text(tr.find('cbc:ReceivedTenderQuantity', NS))
    try:
        num_ofertas = int(num_ofertas) if num_ofertas else None
    except (ValueError, TypeError):
        num_ofertas = None

    fecha_adj = _text(tr.find('cbc:AwardDate', NS))

    importe_adj = None
    lmt = tr.find('cac:LegalMonetaryTotal', NS)
    if lmt is not None:
        importe_adj = _text(lmt.find('cbc:TaxExclusiveAmount', NS))

    return adjudicatario, num_ofertas, fecha_adj, importe_adj


def _extract_location(entry, organo, texto_completo):
    for elem in entry.iter():
        if elem.tag.split('}')[-1] == 'CountrySubentity' and elem.text:
            return elem.text.strip().capitalize()
    for elem in entry.iter():
        if elem.tag.split('}')[-1] == 'CityName' and elem.text:
            city = elem.text.strip()
            city = re.split(r'[.\-–]', city)[0].strip()
            if city and len(city) > 1:
                return city.capitalize()
    texto_geo = f"{organo} {texto_completo}".upper()
    for loc in MAPA_LOCALIDADES:
        if loc in texto_geo:
            return loc.capitalize()
    for kw in ["AYUNTAMIENTO DE ", "CONCELLO DE ", "ALCALDÍA DE "]:
        if kw in texto_geo:
            partes = texto_geo.split(kw)
            if len(partes) > 1:
                return partes[1].split()[0].strip(",.()").capitalize()
    return "No especificada"


def _classify_contract(title, type_code):
    if type_code and type_code in MAPA_TIPO_CONTRATO:
        return MAPA_TIPO_CONTRATO[type_code]
    t = title.lower()
    if 'servicio' in t: return 'Servicios'
    if 'obra' in t: return 'Obras'
    if 'suministro' in t: return 'Suministros Generales'
    return 'Servicios'


def _parse_entry(entry, updated_date):
    """Parsea una entry del feed Atom y devuelve un dict con los datos."""
    title = _text(entry.find('atom:title', NS)) or "Sin título"
    expediente = _text(entry.find('.//cbc:ContractFolderID', NS)) or "No disponible"

    # ── URL directa a la licitación (deep link oficial de la PCSP) ──
    url_licitacion = None
    for link in entry.findall('atom:link', NS):
        href = link.get('href', '')
        if 'deeplink:detalle_licitacion' in href:
            url_licitacion = href
            break
    # Fallback: buscar en atributos href de cualquier elemento
    if not url_licitacion:
        for elem in entry.iter():
            href = elem.get('href', '')
            if 'deeplink:detalle_licitacion' in href:
                url_licitacion = href
                break

    presupuesto_base = None
    for xpath in ['.//cbc:TaxExclusiveAmount',
                   './/cac:EstimatedOverallContractAmount/cbc:TaxExclusiveAmount']:
        tag = entry.find(xpath, NS)
        if tag is not None and tag.text:
            try: presupuesto_base = float(tag.text)
            except ValueError: pass
            break

    organo = _find_first(entry, [
        './/cac:ContractingParty/cac:PartyName/cbc:Name',
        './/cac:PartyName/cbc:Name',
        './/cbc:PartyName/cbc:Name',
    ]) or "Órgano no identificado"

    estado_code = _text(entry.find('.//cbc:ContractFolderStatusCode', NS))
    estado = MAPA_ESTADO.get(estado_code, estado_code or 'Publicado')

    adjudicatario, num_ofertas, fecha_adj, importe_adj = _extract_tender_results(entry)

    try:
        importe_final = float(importe_adj) if importe_adj else (float(presupuesto_base) if presupuesto_base else 0.0)
    except (ValueError, TypeError):
        importe_final = float(presupuesto_base) if presupuesto_base else 0.0

    try:
        presupuesto_base_f = float(presupuesto_base) if presupuesto_base else 0.0
    except (ValueError, TypeError):
        presupuesto_base_f = 0.0

    type_code = _text(entry.find('.//cbc:ContractTypeCode', NS))
    categoria = _classify_contract(title, type_code)
    proc_code = _text(entry.find('.//cbc:ProcedureCode', NS))
    procedimiento = MAPA_PROCEDIMIENTO.get(proc_code, 'Abierto')

    texto_completo = f"{title} {_text(entry.find('atom:summary', NS)) or ''}"
    ubicacion = _extract_location(entry, organo, texto_completo)

    return {
        "ID_Expediente": expediente, "Año": updated_date.year,
        "Objeto": title, "Organo Contratacion": organo,
        "Categoría": categoria, "Tipo Contrato": categoria,
        "Procedimiento": procedimiento, "Estado": estado,
        "Ubicación": ubicacion,
        "URL Licitacion": url_licitacion or "",
        "Presupuesto Base": presupuesto_base_f, "Importe": importe_final,
        "Adjudicatario": adjudicatario or "No adjudicado aún",
        "Num Ofertas": num_ofertas if num_ofertas is not None else 0,
        "Fecha Adjudicacion": fecha_adj if fecha_adj else "Pendiente de adjudicación",
        "Fecha Anuncio": updated_date,
        "Fecha Inicio": "No disponible",
        "Fecha Fin": "No disponible",
        "Fecha Creacion Adjudicatario": "No disponible",
        "Importe Modificaciones": 0.0,
        "Prorrogas Exhaustas": False,
        "Extension Irregular": False,
        "Dias Pago Promedio": 0,
        "Notas Adjudicatario": f"Fuente: feed Atom PCSP ({updated_date.strftime('%Y-%m-%d')})",
    }


def _fetch_feed_url(url):
    """Descarga y parsea una URL de feed Atom. Retorna (root_element, next_url)."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; periodismo-datos/1.0)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    next_url = None
    for link in root.findall('{http://www.w3.org/2005/Atom}link'):
        if link.get('rel') == 'next':
            next_url = link.get('href')
            break
    return root, next_url


# ─── Función principal ───────────────────────────────────────────────────────

def extraer_datos_reales(dias=15, max_paginas=4):
    """
    Se conecta al feed Atom de la PCSP y extrae licitaciones.
    Sigue la cadena de paginación histórica (rel=next) hasta max_paginas.

    Parámetros
    ----------
    dias : int
        Ventana de días hacia atrás para filtrar entradas.
    max_paginas : int
        Máximo de páginas del feed a descargar (cada página ~500 contratos).
        Con 4 páginas se obtienen ~2000 contratos.

    Retorna
    -------
    pd.DataFrame con los contratos extraídos (datos 100% reales).
    """
    archivo_cache = "contratos_reales_temp.csv"
    url_base = (
        "https://contrataciondelestado.es/sindicacion/sindicacion_643/"
        "licitacionesPerfilesContratanteCompleto3.atom"
    )

    # ── Caché (6h para multi-página) ─────────────────────────────────────
    if os.path.exists(archivo_cache):
        tiempo_mod = datetime.fromtimestamp(os.path.getmtime(archivo_cache))
        if datetime.now() - tiempo_mod < timedelta(hours=6):
            return pd.read_csv(archivo_cache)

    fecha_limite = datetime.now() - timedelta(days=dias)
    todos_los_datos = []
    expedientes_vistos = set()
    stats = {
        'total_entries': 0, 'in_window': 0,
        'con_adjudicatario': 0, 'con_ofertas': 0, 'pages': 0,
    }

    next_url = url_base

    for page_num in range(max_paginas):
        if not next_url:
            break

        try:
            root, next_url = _fetch_feed_url(next_url)
            stats['pages'] += 1
        except Exception as e:
            print(f"[extractor] Error en página {page_num}: {e}")
            break

        entries = root.findall('atom:entry', NS)
        page_entries = 0

        for entry in entries:
            stats['total_entries'] += 1

            updated_str = _text(entry.find('atom:updated', NS))
            if updated_str:
                try: updated_date = datetime.strptime(updated_str[:10], "%Y-%m-%d")
                except ValueError: updated_date = datetime.now()
            else:
                updated_date = datetime.now()

            if updated_date < fecha_limite:
                continue

            row = _parse_entry(entry, updated_date)

            # Deduplicación por expediente
            if row['ID_Expediente'] in expedientes_vistos:
                continue
            expedientes_vistos.add(row['ID_Expediente'])

            stats['in_window'] += 1
            if row['Adjudicatario'] != 'No adjudicado aún':
                stats['con_adjudicatario'] += 1
            if row['Num Ofertas'] > 0:
                stats['con_ofertas'] += 1

            todos_los_datos.append(row)
            page_entries += 1

        print(f"[extractor] Pág {page_num+1}/{max_paginas}: {page_entries} nuevas "
              f"(total acumulado: {stats['in_window']})")

        # Si no hay next_url o la página no trajo nada nuevo, paramos
        if not next_url or page_entries == 0:
            break

        # Respeto entre páginas
        if page_num < max_paginas - 1:
            time.sleep(0.5)

    # ── DataFrame ─────────────────────────────────────────────────────────
    df = pd.DataFrame(todos_los_datos)

    if not df.empty:
        if 'Fecha Adjudicacion' in df.columns:
            mask = df['Fecha Adjudicacion'] != 'Pendiente de adjudicación'
            df.loc[mask, 'Fecha Adjudicacion'] = pd.to_datetime(
                df.loc[mask, 'Fecha Adjudicacion'], errors='coerce'
            ).dt.strftime('%Y-%m-%d')
        df.to_csv(archivo_cache, index=False)

    print(f"[extractor] RESUMEN: {stats['pages']} páginas, "
          f"{stats['total_entries']} entries totales, "
          f"{stats['in_window']} únicos en ventana de {dias}d, "
          f"{stats['con_adjudicatario']} con adjudicatario real, "
          f"{stats['con_ofertas']} con nº de ofertas real.")

    return df
