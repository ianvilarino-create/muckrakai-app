# =============================================================================
# Archivo: auditoria_alertas.py
# Autor: Ian Vilariño Vicente
# Revisión: 2026-07-09 — Auditoría con datos reales, sin simulación
# Qué hace: Criterios y algoritmos de NLP para la detección de irregularidades.
# Licencia: MIT
# =============================================================================

import pandas as pd
import numpy as np
import spacy
from datetime import datetime

# ─── Carga del modelo NLP ────────────────────────────────────────────────────
try:
    nlp = spacy.load("es_core_news_sm")
except OSError:
    nlp = None


# ─── Constantes ──────────────────────────────────────────────────────────────
LIMITE_MENOR_SERVICIOS = 15_000
LIMITE_MENOR_OBRAS = 40_000
UMBRAL_BAJA_TEMERARIA = 0.25
UMBRAL_MODIFICADO = 0.20
UMBRAL_RETRASO_INICIO = 90
UMBRAL_PAGO_RAPIDO = 5
UMBRAL_PLAZO_CORTO = 5
UMBRAL_EMPRESA_NUEVA = 365


def _es_dato_real(valor):
    """Determina si un valor es un dato real (no es marcador de 'no disponible')."""
    if valor is None or pd.isna(valor):
        return False
    if isinstance(valor, str) and valor.lower() in (
        'no disponible', 'pendiente de adjudicación', ''
    ):
        return False
    return True


def auditar_contratos(df):
    """
    Ejecuta 13 Red Flags sobre un DataFrame de contratos.
    Solo dispara alertas cuando hay DATOS REALES disponibles.
    Las alertas que requieren datos no disponibles en el feed Atom
    simplemente no se disparan (no generan falsos positivos).

    Retorna el DataFrame con columnas 'Red Flags' y 'Num Red Flags'.
    """
    df = df.copy()

    df['Red Flags'] = [[] for _ in range(len(df))]
    df['Num Red Flags'] = 0

    # Asegurar tipos de fecha
    date_cols = ['Fecha Anuncio', 'Fecha Adjudicacion', 'Fecha Inicio',
                 'Fecha Fin', 'Fecha Creacion Adjudicatario']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', format='mixed', dayfirst=False)

    nlp_cache = {}

    for i, row in df.iterrows():
        alertas = []
        procedimiento = str(row.get('Procedimiento', ''))
        importe = row.get('Importe', 0) or row.get('Presupuesto Base', 0) or 0
        try:
            importe = float(importe)
        except (ValueError, TypeError):
            importe = 0.0

        # ─── F01: Contrato menor al límite legal ────────────────────────
        if 'Menor' in procedimiento or 'simplificado abreviado' in procedimiento.lower():
            tipo = str(row.get('Tipo Contrato', ''))
            if 'Obra' in tipo and importe > LIMITE_MENOR_OBRAS:
                alertas.append(('F01',
                    f'Contrato de obras por {importe:,.0f}€ en procedimiento que puede superar límite legal (40k)'))
            elif importe > LIMITE_MENOR_SERVICIOS:
                alertas.append(('F01',
                    f'Contrato por {importe:,.0f}€ en procedimiento que puede superar límite legal (15k)'))

        # ─── F03: Objeto genérico ───────────────────────────────────────
        objeto = str(row.get('Objeto', '')).lower()
        if any(p in objeto for p in ['varios', 'diversos', 'otros', 'vario', 'diverso']):
            alertas.append(('F03', 'Objeto del contrato excesivamente genérico o impreciso'))

        # ─── F04: Plazo de ejecución corto ──────────────────────────────
        fecha_ini = row.get('Fecha Inicio')
        fecha_fin = row.get('Fecha Fin')
        if pd.notnull(fecha_ini) and pd.notnull(fecha_fin):
            try:
                dias_ejecucion = (fecha_fin - fecha_ini).days
                if 0 < dias_ejecucion < UMBRAL_PLAZO_CORTO:
                    alertas.append(('F04', f'Plazo de ejecución muy corto ({dias_ejecucion} días)'))
            except Exception:
                pass

        # ─── F05: Marcas/patentes en el objeto (NLP) ────────────────────
        if nlp and pd.notna(row.get('Objeto')):
            obj_text = str(row['Objeto'])
            if obj_text not in nlp_cache:
                doc = nlp(obj_text)
                nlp_cache[obj_text] = [ent.text for ent in doc.ents
                                       if ent.label_ in ('MISC', 'ORG', 'PER')]
            ents = nlp_cache[obj_text]
            if ents:
                alertas.append(('F05', f'Posible mención a marca/patente: {", ".join(ents[:3])}'))

        # ─── F06: Baja temeraria ────────────────────────────────────────
        presupuesto = row.get('Presupuesto Base', 0)
        try:
            presupuesto = float(presupuesto) if presupuesto else 0.0
        except (ValueError, TypeError):
            presupuesto = 0.0
        if presupuesto > 0 and importe > 0:
            baja = (presupuesto - importe) / presupuesto
            if baja > UMBRAL_BAJA_TEMERARIA:
                alertas.append(('F06',
                    f'Baja temeraria: {baja:.1%} de descuento ({presupuesto:,.0f}€ → {importe:,.0f}€)'))

        # ─── F07: Único postor en abierto ───────────────────────────────
        num_ofertas = row.get('Num Ofertas', 0)
        try:
            num_ofertas = int(num_ofertas) if num_ofertas else 0
        except (ValueError, TypeError):
            num_ofertas = 0
        if 'Abierto' in procedimiento and 'simplificado' not in procedimiento.lower():
            if num_ofertas == 1:
                alertas.append(('F07', 'Único postor en procedimiento abierto (posible falta de concurrencia)'))

        # ─── F08: Empresa recién creada ─────────────────────────────────
        fecha_adj = row.get('Fecha Adjudicacion')
        fecha_crea = row.get('Fecha Creacion Adjudicatario')
        if _es_dato_real(fecha_crea) and pd.notnull(fecha_adj) and pd.notnull(fecha_crea):
            try:
                antiguedad = (fecha_adj - fecha_crea).days
                if antiguedad < UMBRAL_EMPRESA_NUEVA:
                    alertas.append(('F08', f'Empresa adjudicataria creada hace <1 año ({antiguedad} días)'))
            except Exception:
                pass

        # ─── F09: UTE anómala ───────────────────────────────────────────
        adjudicatario = str(row.get('Adjudicatario', ''))
        notas = str(row.get('Notas Adjudicatario', ''))
        if 'UTE' in adjudicatario.upper() and 'sin experiencia' in notas.lower():
            alertas.append(('F09', 'UTE con indicios de socio sin experiencia'))

        # ─── F10: Modificado > 20% ──────────────────────────────────────
        importe_mod = row.get('Importe Modificaciones', 0)
        try:
            importe_mod = float(importe_mod) if importe_mod else 0.0
        except (ValueError, TypeError):
            importe_mod = 0.0
        if importe_mod > 0 and importe > 0 and (importe_mod / importe) > UMBRAL_MODIFICADO:
            alertas.append(('F10', f'Modificación del {importe_mod/importe:.1%} supera el 20% del importe inicial'))

        # ─── F11: Prórrogas anómalas ────────────────────────────────────
        if row.get('Prorrogas Exhaustas') and row.get('Extension Irregular'):
            alertas.append(('F11', 'Extensión de contrato irregular tras agotar prórrogas'))

        # ─── F12: Retraso en inicio > 3 meses ───────────────────────────
        if pd.notnull(fecha_adj) and pd.notnull(fecha_ini):
            try:
                retraso = (fecha_ini - fecha_adj).days
                if retraso > UMBRAL_RETRASO_INICIO:
                    alertas.append(('F12', f'Retraso de inicio de {retraso} días (>3 meses) desde adjudicación'))
            except Exception:
                pass

        # ─── F13: Pago rápido ───────────────────────────────────────────
        dias_pago = row.get('Dias Pago Promedio', 99)
        try:
            dias_pago = int(dias_pago) if dias_pago else 99
        except (ValueError, TypeError):
            dias_pago = 99
        if 0 < dias_pago <= UMBRAL_PAGO_RAPIDO:
            alertas.append(('F13', f'Pago en {dias_pago} días: inusualmente rápido'))

        # ── Asignar ────────────────────────────────────────────────────
        df.at[i, 'Red Flags'] = alertas
        df.at[i, 'Num Red Flags'] = len(alertas)

    # ─── F02: Fraccionamiento (regla grupal) ────────────────────────────
    menores = df[df['Procedimiento'].str.contains('Menor|simplificado abreviado', case=False, na=False)]
    # Excluir contratos sin adjudicatario real (no se puede evaluar fraccionamiento)
    menores = menores[menores['Adjudicatario'] != 'No adjudicado aún']
    for (adj, org), group in menores.groupby(['Adjudicatario', 'Organo Contratacion']):
        if len(group) > 1:
            total_importe = group['Importe'].sum()
            if total_importe > LIMITE_MENOR_SERVICIOS:
                for idx in group.index:
                    alerta_f02 = ('F02',
                        f'Posible fraccionamiento: {len(group)} contratos al mismo adjudicatario suman {total_importe:,.0f}€')
                    if alerta_f02 not in df.at[idx, 'Red Flags']:
                        df.at[idx, 'Red Flags'].append(alerta_f02)
                        df.at[idx, 'Num Red Flags'] += 1

    return df
