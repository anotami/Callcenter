"""
Generador de graficas interactivas con Plotly para todos los agentes.
Detecta automaticamente el tipo de datos y genera los graficos mas adecuados.
Exporta a PDF con kaleido.
"""

import io
import json
import logging
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

logger = logging.getLogger("callcenter.charts")

# ── Paleta de colores corporativa ─────────────────────────────────────────
COLORS = {
    "primary": "#4A90D9",
    "secondary": "#7B68EE",
    "success": "#28A745",
    "warning": "#FFC107",
    "danger": "#DC3545",
    "info": "#17A2B8",
    "orange": "#FF6B35",
    "dark": "#343A40",
    "light": "#F8F9FA",
}

PALETTE = [
    "#4A90D9", "#7B68EE", "#28A745", "#FF6B35", "#FFC107",
    "#DC3545", "#17A2B8", "#6F42C1", "#E83E8C", "#20C997",
    "#FD7E14", "#6610F2", "#007BFF", "#6C757D",
]

_SEMAFORO_COLORS = {"verde": "#28A745", "amarillo": "#FFC107", "rojo": "#DC3545"}

# ── Layout base ──────────────────────────────────────────────────────────

_BASE_LAYOUT = dict(
    font=dict(family="Segoe UI, Roboto, sans-serif", size=12),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=60, r=30, t=50, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    hoverlabel=dict(bgcolor="white", font_size=12),
)


def _apply_layout(fig, title: str = "", height: int = 420):
    """Aplica el layout base corporativo a una figura."""
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=COLORS["dark"]), x=0.01),
        height=height,
        **_BASE_LAYOUT,
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.06)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.06)")
    return fig


# ══════════════════════════════════════════════════════════════════════════
#  Graficos genericos (reutilizables por todos los agentes)
# ══════════════════════════════════════════════════════════════════════════


def chart_bar(df: pd.DataFrame, x: str, y: str, title: str = "",
              color: str | None = None, orientation: str = "v") -> go.Figure:
    """Grafico de barras con estilo corporativo."""
    if orientation == "h":
        fig = px.bar(df, y=x, x=y, color=color, color_discrete_sequence=PALETTE,
                     orientation="h")
    else:
        fig = px.bar(df, x=x, y=y, color=color, color_discrete_sequence=PALETTE)
    return _apply_layout(fig, title)


def chart_line(df: pd.DataFrame, x: str, y: str | list[str],
               title: str = "") -> go.Figure:
    """Grafico de lineas (una o multiples series)."""
    if isinstance(y, list):
        fig = go.Figure()
        for i, col in enumerate(y):
            fig.add_trace(go.Scatter(
                x=df[x], y=df[col], mode="lines+markers", name=col,
                line=dict(color=PALETTE[i % len(PALETTE)], width=2),
                marker=dict(size=6),
            ))
    else:
        fig = px.line(df, x=x, y=y, color_discrete_sequence=PALETTE, markers=True)
    return _apply_layout(fig, title)


def chart_pie(df: pd.DataFrame, names: str, values: str,
              title: str = "") -> go.Figure:
    """Grafico de torta / donut."""
    fig = px.pie(df, names=names, values=values, color_discrete_sequence=PALETTE,
                 hole=0.4)
    fig.update_traces(textinfo="label+percent", textfont_size=11)
    return _apply_layout(fig, title, height=380)


def chart_heatmap(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Heatmap para matrices de correlacion o distribucion."""
    num_df = df.select_dtypes(include="number")
    if num_df.empty:
        return go.Figure()
    corr = num_df.corr()
    fig = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                    zmin=-1, zmax=1)
    return _apply_layout(fig, title or "Correlacion entre Metricas", height=500)


def chart_radar(categories: list[str], values: list[float],
                title: str = "", max_val: float | None = None) -> go.Figure:
    """Grafico radar / spider para comparacion de KPIs."""
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        fillcolor=f"rgba(74, 144, 217, 0.2)",
        line=dict(color=COLORS["primary"], width=2),
        marker=dict(size=6),
    ))
    range_max = max_val or (max(values) * 1.2 if values else 100)
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, range_max],
                            gridcolor="rgba(0,0,0,0.1)"),
            angularaxis=dict(gridcolor="rgba(0,0,0,0.1)"),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    return _apply_layout(fig, title, height=450)


def chart_gauge(value: float, title: str = "", max_val: float = 100,
                thresholds: dict | None = None) -> go.Figure:
    """Indicador tipo gauge / velocimetro."""
    if thresholds is None:
        thresholds = {"bueno": 80, "medio": 60}
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title=dict(text=title, font=dict(size=14)),
        gauge=dict(
            axis=dict(range=[0, max_val]),
            bar=dict(color=COLORS["primary"]),
            steps=[
                dict(range=[0, thresholds.get("medio", 60)], color="#FFEBEE"),
                dict(range=[thresholds.get("medio", 60), thresholds.get("bueno", 80)], color="#FFF9C4"),
                dict(range=[thresholds.get("bueno", 80), max_val], color="#E8F5E9"),
            ],
            threshold=dict(
                line=dict(color=COLORS["danger"], width=3),
                thickness=0.8, value=thresholds.get("bueno", 80),
            ),
        ),
    ))
    return _apply_layout(fig, height=280)


def chart_box(df: pd.DataFrame, y: str, x: str | None = None,
              title: str = "") -> go.Figure:
    """Box plot para distribucion de metricas."""
    fig = px.box(df, y=y, x=x, color=x, color_discrete_sequence=PALETTE)
    return _apply_layout(fig, title)


def chart_histogram(df: pd.DataFrame, col: str, title: str = "",
                    nbins: int = 30) -> go.Figure:
    """Histograma de distribucion."""
    fig = px.histogram(df, x=col, nbins=nbins, color_discrete_sequence=[COLORS["primary"]])
    fig.update_traces(marker_line_color=COLORS["dark"], marker_line_width=0.5)
    return _apply_layout(fig, title or f"Distribucion de {col}")


def chart_scatter(df: pd.DataFrame, x: str, y: str,
                  color: str | None = None, size: str | None = None,
                  title: str = "") -> go.Figure:
    """Scatter plot con burbujas opcionales."""
    fig = px.scatter(df, x=x, y=y, color=color, size=size,
                     color_discrete_sequence=PALETTE)
    return _apply_layout(fig, title)


def chart_waterfall(names: list[str], values: list[float],
                    title: str = "") -> go.Figure:
    """Grafico waterfall para descomponer valores."""
    measures = ["relative"] * (len(values) - 1) + ["total"]
    fig = go.Figure(go.Waterfall(
        x=names, y=values, measure=measures,
        connector=dict(line=dict(color="rgb(63,63,63)", width=1)),
        increasing=dict(marker=dict(color=COLORS["success"])),
        decreasing=dict(marker=dict(color=COLORS["danger"])),
        totals=dict(marker=dict(color=COLORS["primary"])),
    ))
    return _apply_layout(fig, title)


def chart_funnel(stages: list[str], values: list[float],
                 title: str = "") -> go.Figure:
    """Grafico de embudo."""
    fig = go.Figure(go.Funnel(
        y=stages, x=values,
        textinfo="value+percent initial",
        marker=dict(color=PALETTE[:len(stages)]),
    ))
    return _apply_layout(fig, title, height=380)


def chart_kpi_cards(kpis: list[dict]) -> go.Figure:
    """Tarjetas de KPI con indicadores (para export PDF)."""
    n = len(kpis)
    cols = min(n, 4)
    rows = (n + cols - 1) // cols
    fig = make_subplots(rows=rows, cols=cols,
                        specs=[[{"type": "indicator"}] * cols for _ in range(rows)])
    for i, kpi in enumerate(kpis):
        r, c = divmod(i, cols)
        sem_color = _SEMAFORO_COLORS.get(kpi.get("semaforo", ""), COLORS["primary"])
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=_safe_float(kpi.get("valor", 0)),
                title=dict(text=kpi.get("nombre", kpi.get("kpi", "?")), font=dict(size=12)),
                number=dict(font=dict(color=sem_color, size=28)),
            ),
            row=r + 1, col=c + 1,
        )
    return _apply_layout(fig, height=180 * rows)


# ══════════════════════════════════════════════════════════════════════════
#  Auto-deteccion: genera graficos a partir de resultados de agentes
# ══════════════════════════════════════════════════════════════════════════


def _safe_float(v) -> float:
    """Convierte un valor a float de forma segura."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _detect_numeric_cols(df: pd.DataFrame) -> list[str]:
    """Detecta columnas numericas relevantes para graficar."""
    return df.select_dtypes(include="number").columns.tolist()


def _detect_category_cols(df: pd.DataFrame) -> list[str]:
    """Detecta columnas categoricas adecuadas para agrupar."""
    cats = []
    for col in df.select_dtypes(include=["object", "category"]).columns:
        nunique = df[col].nunique()
        if 2 <= nunique <= 50:
            cats.append(col)
    return cats


def auto_charts_from_dataframe(df: pd.DataFrame, title_prefix: str = "") -> list[go.Figure]:
    """Genera graficos automaticos a partir de un DataFrame."""
    figs = []
    num_cols = _detect_numeric_cols(df)
    cat_cols = _detect_category_cols(df)

    if not num_cols:
        return figs

    # 1. Si hay columna temporal, linea de tendencia
    time_cols = [c for c in df.columns if any(k in c.lower() for k in
                 ["fecha", "periodo", "date", "mes", "semana", "intervalo"])]
    if time_cols and num_cols:
        tc = time_cols[0]
        top_metrics = num_cols[:4]
        fig = chart_line(df.sort_values(tc), tc, top_metrics,
                         f"{title_prefix}Tendencia Temporal")
        figs.append(fig)

    # 2. Si hay categorias, barras agrupadas
    if cat_cols and num_cols:
        cat = cat_cols[0]
        metric = num_cols[0]
        agg = df.groupby(cat, as_index=False)[metric].sum().sort_values(metric, ascending=False)
        if len(agg) <= 25:
            figs.append(chart_bar(agg, cat, metric,
                                  f"{title_prefix}{metric} por {cat}"))

    # 3. Distribucion de top metrica
    if num_cols and len(df) > 5:
        figs.append(chart_histogram(df, num_cols[0],
                                    f"{title_prefix}Distribucion de {num_cols[0]}"))

    # 4. Si hay multiples categorias, pie de la primera
    if cat_cols and num_cols:
        cat = cat_cols[0]
        metric = num_cols[0]
        agg = df.groupby(cat, as_index=False)[metric].sum()
        if 2 <= len(agg) <= 12:
            figs.append(chart_pie(agg, cat, metric,
                                  f"{title_prefix}Composicion: {metric} por {cat}"))

    # 5. Box plot por categoria si hay agrupacion
    if cat_cols and num_cols and len(df) > 10:
        figs.append(chart_box(df, num_cols[0], cat_cols[0],
                              f"{title_prefix}Distribucion de {num_cols[0]} por {cat_cols[0]}"))

    # 6. Heatmap de correlacion si hay 3+ numericas
    if len(num_cols) >= 3:
        figs.append(chart_heatmap(df, f"{title_prefix}Correlacion entre Metricas"))

    return figs


def auto_charts_from_result(data: dict, agent_id: str = "") -> list[go.Figure]:
    """Genera graficos automaticamente a partir del resultado de un agente."""
    figs = []

    # ── KPIs como radar ──
    kpis = data.get("kpis")
    if isinstance(kpis, list) and kpis:
        names = [k.get("nombre", k.get("kpi", "?")) for k in kpis]
        vals = [_safe_float(k.get("valor", 0)) for k in kpis]
        if names and all(v >= 0 for v in vals):
            figs.append(chart_radar(names, vals, "KPIs del Periodo"))

    elif isinstance(kpis, dict) and kpis:
        # kpis como dict con stats (ej: ingesta_wfm)
        names = list(kpis.keys())[:10]
        vals = [_safe_float(kpis[n].get("promedio", 0)) for n in names]
        if names:
            figs.append(chart_radar(names, vals, "Promedio de KPIs"))

    # ── Dashboard KPIs como tarjetas ──
    dash_kpis = data.get("dashboard_kpis")
    if isinstance(dash_kpis, list) and dash_kpis:
        figs.append(chart_kpi_cards(dash_kpis))

    # ── Distribucion de cuartiles ──
    cuartiles = data.get("distribucion_cuartiles")
    if isinstance(cuartiles, dict) and cuartiles:
        for metric_name, dist in list(cuartiles.items())[:4]:
            labels = list(dist.keys())
            values = [int(v) for v in dist.values()]
            df_q = pd.DataFrame({"Cuartil": labels, "Cantidad": values})
            figs.append(chart_bar(df_q, "Cuartil", "Cantidad",
                                  f"Distribucion Cuartil: {metric_name}"))

    # ── Resumen por proveedor ──
    prov = data.get("resumen_por_proveedor")
    if isinstance(prov, dict) and prov:
        df_prov = pd.DataFrame.from_dict(prov, orient="index")
        df_prov.index.name = "PROVEEDOR"
        df_prov = df_prov.reset_index()
        num_cols = df_prov.select_dtypes(include="number").columns.tolist()
        if "ATENDIDAS" in num_cols:
            figs.append(chart_bar(df_prov, "PROVEEDOR", "ATENDIDAS",
                                  "Llamadas Atendidas por Proveedor"))
            figs.append(chart_pie(df_prov, "PROVEEDOR", "ATENDIDAS",
                                  "Composicion por Proveedor"))
        if "TMO" in num_cols:
            figs.append(chart_bar(df_prov, "PROVEEDOR", "TMO",
                                  "TMO Promedio por Proveedor"))

    # ── Resumen por plataforma ──
    plat = data.get("resumen_por_plataforma")
    if isinstance(plat, dict) and plat:
        df_plat = pd.DataFrame.from_dict(plat, orient="index")
        df_plat.index.name = "PLATAFORMA"
        df_plat = df_plat.reset_index()
        num_cols = df_plat.select_dtypes(include="number").columns.tolist()
        if "ATENDIDAS" in num_cols:
            figs.append(chart_bar(df_plat, "PLATAFORMA", "ATENDIDAS",
                                  "Llamadas Atendidas por Plataforma"))

    # ── Dimensiones (top 10 values) ──
    dims = data.get("dimensiones")
    if isinstance(dims, dict):
        for dim_name, dim_data in list(dims.items())[:3]:
            top = dim_data.get("top_10", {})
            if top and len(top) >= 2:
                df_dim = pd.DataFrame({
                    dim_name: list(top.keys()),
                    "Registros": list(top.values()),
                })
                figs.append(chart_bar(df_dim, dim_name, "Registros",
                                      f"Top 10: {dim_name}"))

    # ── Alertas como funnel ──
    alertas = data.get("alertas")
    if isinstance(alertas, list) and len(alertas) >= 2:
        stages = [a.get("tipo", a.get("mensaje", "?"))[:30] for a in alertas]
        values = [a.get("cantidad", 1) for a in alertas]
        if all(isinstance(v, (int, float)) for v in values):
            figs.append(chart_funnel(stages, values, "Alertas Detectadas"))

    # ── Staffing result ──
    staffing = data.get("resultado")
    if isinstance(staffing, dict) and "agentes_minimos" in staffing:
        names = ["Agentes Minimos", "Con Shrinkage"]
        vals = [staffing["agentes_minimos"], staffing["agentes_con_shrinkage"]]
        df_staff = pd.DataFrame({"Concepto": names, "Cantidad": vals})
        figs.append(chart_bar(df_staff, "Concepto", "Cantidad", "Staffing Requerido"))

        ocu = staffing.get("ocupacion_pct", 0)
        if ocu:
            figs.append(chart_gauge(ocu, "Ocupacion %"))

        nds = staffing.get("nivel_servicio_proyectado", 0)
        if nds:
            figs.append(chart_gauge(nds, "Nivel de Servicio %"))

    # ── Evaluacion de llamada ──
    if "evaluacion" in data or "puntaje_total" in data:
        score = data.get("puntaje_total", 0)
        if score:
            figs.append(chart_gauge(float(score), "Puntaje de Calidad"))

    # ── Errores criticos ──
    errores = data.get("errores_criticos")
    if isinstance(errores, list) and errores:
        severidades = {}
        for e in errores:
            sev = e.get("severidad", "?")
            severidades[sev] = severidades.get(sev, 0) + 1
        df_err = pd.DataFrame({
            "Severidad": list(severidades.keys()),
            "Cantidad": list(severidades.values()),
        })
        figs.append(chart_pie(df_err, "Severidad", "Cantidad", "Errores por Severidad"))

    # ── Facturacion (lineas) ──
    lineas = data.get("lineas")
    if isinstance(lineas, list) and lineas:
        df_fac = pd.DataFrame(lineas)
        if "subtotal" in df_fac.columns and "concepto" in df_fac.columns:
            figs.append(chart_bar(df_fac, "concepto", "subtotal",
                                  "Facturacion por Concepto"))

    # ── KPIs evaluados (bonos/penalidades) ──
    kpis_eval = data.get("kpis_evaluados") or data.get("slas_evaluados")
    if isinstance(kpis_eval, list) and kpis_eval:
        names = [k.get("kpi", k.get("sla", "?")) for k in kpis_eval]
        vals = [_safe_float(k.get("pct_cumplimiento", k.get("valor_real", 0))) for k in kpis_eval]
        if names:
            figs.append(chart_radar(names, vals, "Cumplimiento de KPIs/SLAs", max_val=120))

    # ── Tiempos de estado ──
    tiempos = data.get("tiempos_estado")
    if isinstance(tiempos, dict) and tiempos:
        names = list(tiempos.keys())
        vals = [_safe_float(tiempos[n].get("promedio", 0)) for n in names]
        df_t = pd.DataFrame({"Tiempo": names, "Promedio (seg)": vals})
        figs.append(chart_bar(df_t, "Tiempo", "Promedio (seg)",
                              "Tiempos de Estado Promedio"))

    # ── Muestra como DataFrame auto-charts ──
    muestra = data.get("muestra")
    if isinstance(muestra, list) and len(muestra) >= 3:
        df_m = pd.DataFrame(muestra)
        auto_figs = auto_charts_from_dataframe(df_m, "Datos: ")
        figs.extend(auto_figs[:3])  # Limitar a 3 graficos de muestra

    return figs


# ══════════════════════════════════════════════════════════════════════════
#  Exportacion a PDF
# ══════════════════════════════════════════════════════════════════════════


def _fig_to_png(fig: go.Figure, width: int = 1000, height: int = 500) -> bytes | None:
    """Intenta convertir una figura a PNG usando kaleido. Retorna None si falla."""
    try:
        return fig.to_image(format="png", width=width, height=height, scale=2)
    except Exception as e:
        logger.debug("kaleido PNG export failed: %s", e)
        return None


def export_charts_to_html(figures: list[go.Figure], title: str = "Reporte",
                          metadata: dict | None = None) -> bytes:
    """Exporta graficos como un HTML interactivo (abrirlo en navegador para imprimir a PDF)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta_line = f"Generado: {now}"
    if metadata:
        if metadata.get("agent_name"):
            meta_line += f" | Agente: {metadata['agent_name']}"
        if metadata.get("skill_name"):
            meta_line += f" | Skill: {metadata['skill_name']}"

    html_parts = [f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{ font-family: 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #fafafa; }}
  h1 {{ color: #4A90D9; border-bottom: 2px solid #4A90D9; padding-bottom: 10px; }}
  .meta {{ color: #6C757D; font-size: 0.9em; margin-bottom: 30px; }}
  .chart-container {{ background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                      padding: 20px; margin-bottom: 30px; page-break-inside: avoid; }}
  @media print {{
    body {{ margin: 20px; }}
    .chart-container {{ box-shadow: none; border: 1px solid #eee; page-break-inside: avoid; }}
    .no-print {{ display: none; }}
  }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">{meta_line}</p>
<p class="no-print" style="background:#E3F2FD;padding:12px;border-radius:6px;">
  Para exportar a PDF: usa <b>Ctrl+P</b> (o Cmd+P en Mac) y selecciona "Guardar como PDF"
</p>
"""]

    for i, fig in enumerate(figures):
        chart_html = fig.to_html(full_html=False, include_plotlyjs=(i == 0),
                                 config={"displayModeBar": True, "responsive": True})
        chart_title = ""
        if fig.layout.title and fig.layout.title.text:
            chart_title = fig.layout.title.text
        html_parts.append(f'<div class="chart-container">')
        if chart_title:
            html_parts.append(f'<h3 style="color:#343A40;margin-top:0">{chart_title}</h3>')
        html_parts.append(chart_html)
        html_parts.append('</div>')

    html_parts.append("</body></html>")
    return "\n".join(html_parts).encode("utf-8")


def export_charts_to_pdf(figures: list[go.Figure], title: str = "Reporte",
                         metadata: dict | None = None) -> bytes:
    """Exporta graficos a PDF.

    Intenta usar kaleido+reportlab para PDF nativo. Si no estan disponibles,
    genera un HTML interactivo que el usuario puede imprimir a PDF desde el navegador.
    """
    # Intentar export nativo con kaleido + reportlab
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch, cm
        from reportlab.platypus import (SimpleDocTemplate, Image, Paragraph, Spacer)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor

        # Verificar que kaleido funciona
        test_png = _fig_to_png(figures[0]) if figures else None
        if test_png:
            return _export_pdf_reportlab(figures, title, metadata)
    except ImportError:
        pass

    # Fallback: HTML interactivo
    return export_charts_to_html(figures, title, metadata)


def _export_pdf_reportlab(figures: list[go.Figure], title: str,
                          metadata: dict | None) -> bytes:
    """Genera PDF con reportlab + kaleido (alta calidad)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=20, textColor=HexColor("#4A90D9"),
        spaceAfter=12,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"],
        fontSize=10, textColor=HexColor("#6C757D"),
        spaceAfter=20,
    )

    story = []
    story.append(Paragraph(title, title_style))
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sub = f"Generado: {now}"
    if metadata:
        if metadata.get("agent_name"):
            sub += f" | Agente: {metadata['agent_name']}"
        if metadata.get("skill_name"):
            sub += f" | Skill: {metadata['skill_name']}"
    story.append(Paragraph(sub, subtitle_style))
    story.append(Spacer(1, 0.3 * inch))

    page_width = A4[0] - 4 * cm
    for i, fig in enumerate(figures):
        img_bytes = _fig_to_png(fig)
        if img_bytes:
            img_buf = io.BytesIO(img_bytes)
            img = Image(img_buf, width=page_width, height=page_width * 0.5)
            story.append(img)
            story.append(Spacer(1, 0.3 * inch))
        else:
            story.append(Paragraph(f"[Grafico {i + 1} - ver version HTML]", styles["Normal"]))
            story.append(Spacer(1, 0.2 * inch))

    doc.build(story)
    return buf.getvalue()


def figures_to_png_zip(figures: list[go.Figure]) -> bytes:
    """Exporta figuras como PNGs en un ZIP. Si kaleido no esta disponible,
    exporta como HTMLs individuales."""
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, fig in enumerate(figures):
            img = _fig_to_png(fig, width=1200, height=600)
            if img:
                zf.writestr(f"grafico_{i + 1:02d}.png", img)
            else:
                # Fallback: export as individual HTML
                html = fig.to_html(full_html=True, include_plotlyjs="cdn",
                                   config={"displayModeBar": True})
                zf.writestr(f"grafico_{i + 1:02d}.html", html.encode("utf-8"))
    return buf.getvalue()
