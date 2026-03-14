"""
Streamlit UI - Sistema de Agentes de Call Center
Interfaz visual donde los agentes son un equipo con habilidades ejecutables.
"""

import streamlit as st
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Agregar directorio base al path
sys.path.insert(0, str(Path(__file__).parent))

from agents_config import get_all_agents, get_agent, get_skill
from agent_runner import execute_skill, load_all_results, load_result_by_file, RESULTS_DIR

# ── Page Config ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CallCenter AI Team",
    layout="wide",
    page_icon="headphones",
    initial_sidebar_state="expanded",
)

# ── CSS Personalizado ──────────────────────────────────────────────────

st.markdown("""
<style>
    /* Agente cards en sidebar */
    .agent-card {
        padding: 12px 16px;
        border-radius: 10px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: all 0.2s;
        border: 2px solid transparent;
    }
    .agent-card:hover {
        transform: translateX(4px);
        border-color: rgba(255,255,255,0.3);
    }
    .agent-card.active {
        border-color: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    .agent-name {
        font-size: 1.1em;
        font-weight: 700;
        color: white;
        margin: 0;
    }
    .agent-desc {
        font-size: 0.8em;
        color: rgba(255,255,255,0.8);
        margin: 4px 0 0 0;
    }

    /* Skill cards */
    .skill-card {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 16px;
        transition: all 0.2s;
    }
    .skill-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .skill-title {
        font-size: 1.15em;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .skill-desc {
        color: #555;
        margin-bottom: 12px;
        line-height: 1.5;
    }
    .data-tag {
        background: #e3f2fd;
        color: #1565c0;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8em;
        display: inline-block;
        margin: 2px 4px 2px 0;
    }
    .result-tag {
        background: #e8f5e9;
        color: #2e7d32;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8em;
        display: inline-block;
    }

    /* History items */
    .history-item {
        background: #fafafa;
        border-left: 4px solid #ddd;
        padding: 10px 14px;
        margin-bottom: 8px;
        border-radius: 0 8px 8px 0;
        font-size: 0.9em;
    }

    /* Ocultar streamlit defaults */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ── Estado de sesion ───────────────────────────────────────────────────

if "selected_agent" not in st.session_state:
    st.session_state.selected_agent = None
if "selected_skill" not in st.session_state:
    st.session_state.selected_skill = None
if "execution_result" not in st.session_state:
    st.session_state.execution_result = None

AGENTS = get_all_agents()

# ── Iconos por agente (Bootstrap Icons disponibles en Streamlit) ──────

AGENT_ICONS = {
    "transcriptor": ":material/mic:",
    "diarizador": ":material/group:",
    "evaluador": ":material/checklist:",
    "atlas": ":material/analytics:",
}

# ── Sidebar: Equipo de Agentes ─────────────────────────────────────────

with st.sidebar:
    st.markdown("### Equipo de Agentes")
    st.caption("Selecciona un agente para ver sus habilidades")
    st.divider()

    for agent_id, agent in AGENTS.items():
        icon = AGENT_ICONS.get(agent_id, ":material/smart_toy:")
        is_selected = st.session_state.selected_agent == agent_id
        label = f"**{agent['nombre']}**"
        if is_selected:
            label = f">> **{agent['nombre']}** <<"

        if st.button(
            f"{agent['nombre']}",
            key=f"agent_{agent_id}",
            use_container_width=True,
            icon=icon,
            type="primary" if is_selected else "secondary",
        ):
            st.session_state.selected_agent = agent_id
            st.session_state.selected_skill = None
            st.session_state.execution_result = None
            st.rerun()

        # Info breve bajo el boton
        st.caption(agent["descripcion"][:80] + "...")
        st.markdown("")

    # ── Historial rapido en sidebar ──
    st.divider()
    st.markdown("### Historial Reciente")
    all_results = load_all_results()
    if all_results:
        for r in all_results[:5]:
            agent_name = r.get("agent_name", "?")
            skill_name = r.get("skill_name", "?")
            fecha = r.get("fecha", "")
            version = r.get("version", 1)
            st.caption(f"{agent_name} / {skill_name} v{version} - {fecha}")
    else:
        st.caption("Sin resultados aun. Ejecuta una habilidad para comenzar.")

# ── Panel Principal ────────────────────────────────────────────────────

if st.session_state.selected_agent is None:
    # Pantalla de bienvenida
    st.markdown("# CallCenter AI Team")
    st.markdown("### Tu equipo de agentes inteligentes para analisis de calidad")
    st.markdown("---")

    cols = st.columns(len(AGENTS))
    for i, (agent_id, agent) in enumerate(AGENTS.items()):
        with cols[i]:
            icon = AGENT_ICONS.get(agent_id, ":material/smart_toy:")
            st.markdown(f"#### {agent['nombre']}")
            st.markdown(agent["descripcion"])
            num_skills = len(agent["habilidades"])
            st.metric("Habilidades", num_skills)

    st.markdown("---")
    st.info("Selecciona un agente en el panel lateral para ver sus habilidades y ejecutarlas.")

    # Resumen de actividad
    if all_results:
        st.markdown("### Actividad del Equipo")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total Tareas Completadas", len(all_results))

        agents_used = set(r.get("agent_id") for r in all_results)
        col_b.metric("Agentes Activos", len(agents_used))

        fechas = set(r.get("fecha") for r in all_results)
        col_c.metric("Dias con Actividad", len(fechas))

else:
    # ── Vista de Agente Seleccionado ───────────────────────────────────
    agent_id = st.session_state.selected_agent
    agent = AGENTS[agent_id]

    st.markdown(f"# {agent['nombre']}")
    st.markdown(agent["descripcion"])
    st.markdown("---")

    # ── Columnas: Skills (izq) + Ejecucion/Resultado (der) ────────────
    col_skills, col_exec = st.columns([1, 2])

    with col_skills:
        st.markdown("### Habilidades")

        for skill in agent["habilidades"]:
            is_selected = st.session_state.selected_skill == skill["id"]
            btn_type = "primary" if is_selected else "secondary"

            if st.button(
                skill["nombre"],
                key=f"skill_{skill['id']}",
                use_container_width=True,
                type=btn_type,
            ):
                st.session_state.selected_skill = skill["id"]
                st.session_state.execution_result = None
                st.rerun()

            # Info compacta
            st.caption(skill["descripcion"][:100])
            st.markdown("")

    with col_exec:
        if st.session_state.selected_skill is None:
            st.info("Selecciona una habilidad a la izquierda para ver sus detalles y ejecutarla.")
        else:
            skill = get_skill(agent_id, st.session_state.selected_skill)
            if not skill:
                st.error("Habilidad no encontrada")
            else:
                # ── Detalle de la habilidad ────────────────────────────
                st.markdown(f"### {skill['nombre']}")
                st.markdown(skill["descripcion"])

                # Datos necesarios
                st.markdown("**Datos necesarios:**")
                for dato in skill["datos_necesarios"]:
                    st.markdown(f"- `{dato}`")

                # Resultado esperado
                st.markdown(f"**Resultado:** {skill['resultado']}")
                st.markdown("---")

                # ── Formulario de Ejecucion ────────────────────────────
                st.markdown("### Ejecutar")

                uploaded_file = None
                input_text = ""
                selected_prev_results = []

                # Input: Archivo
                if skill.get("acepta_archivo"):
                    exts = skill.get("extensiones", [])
                    uploaded_file = st.file_uploader(
                        f"Archivo ({', '.join(exts)})",
                        type=[e.lstrip(".") for e in exts],
                        key=f"upload_{skill['id']}",
                    )

                # Input: Texto
                if skill.get("acepta_texto"):
                    input_text = st.text_area(
                        "Texto / Dialogo",
                        height=150,
                        placeholder="Pega aqui el texto o dialogo a procesar...",
                        key=f"text_{skill['id']}",
                    )

                # Input: Resultado previo de otro agente
                if skill.get("acepta_resultado_previo"):
                    compatible = skill.get("agentes_compatibles", [])
                    is_multi = skill.get("multi_resultado", False)

                    # Cargar resultados disponibles de agentes compatibles
                    prev_results = []
                    for compat_agent in compatible:
                        prev_results.extend(load_all_results(compat_agent))

                    # Para Atlas resumen_equipo, incluir todos
                    if skill["id"] == "resumen_equipo":
                        prev_results = load_all_results()

                    if prev_results:
                        st.markdown("**Resultados previos disponibles:**")
                        options = []
                        for r in prev_results:
                            label = (
                                f"{r.get('agent_name', '?')} / "
                                f"{r.get('skill_name', '?')} v{r.get('version', 1)} "
                                f"- {r.get('fecha', '')}"
                            )
                            options.append(label)

                        if is_multi:
                            selected_indices = st.multiselect(
                                "Selecciona resultados (2 o mas para Atlas)",
                                range(len(options)),
                                format_func=lambda i: options[i],
                                key=f"multi_{skill['id']}",
                            )
                            selected_prev_results = [prev_results[i] for i in selected_indices]
                        else:
                            selected_idx = st.selectbox(
                                "Selecciona un resultado previo",
                                range(len(options)),
                                format_func=lambda i: options[i],
                                key=f"single_{skill['id']}",
                            )
                            if selected_idx is not None:
                                selected_prev_results = [prev_results[selected_idx]]
                    else:
                        st.caption(
                            "No hay resultados previos disponibles. "
                            "Ejecuta primero una habilidad de los agentes compatibles."
                        )

                # ── Boton de ejecucion ─────────────────────────────────
                st.markdown("")
                can_execute = (
                    uploaded_file is not None
                    or len(input_text.strip()) > 0
                    or len(selected_prev_results) > 0
                )

                if st.button(
                    f"Ejecutar: {skill['nombre']}",
                    disabled=not can_execute,
                    use_container_width=True,
                    type="primary",
                    key=f"exec_{skill['id']}",
                ):
                    with st.spinner(f"Ejecutando {skill['nombre']}..."):
                        # Preparar argumentos
                        audio_bytes = None
                        filename = ""
                        if uploaded_file:
                            audio_bytes = uploaded_file.read()
                            filename = uploaded_file.name

                        resultado_previo = None
                        if selected_prev_results and not skill.get("multi_resultado"):
                            resultado_previo = selected_prev_results[0].get("resultado")

                        result = execute_skill(
                            agent_id=agent_id,
                            skill_id=skill["id"],
                            skill_name=skill["nombre"],
                            audio_bytes=audio_bytes,
                            filename=filename,
                            texto=input_text,
                            resultado_previo=resultado_previo,
                            resultados_multiples=selected_prev_results if skill.get("multi_resultado") else None,
                        )
                        st.session_state.execution_result = result

                # ── Mostrar resultado ──────────────────────────────────
                if st.session_state.execution_result:
                    result = st.session_state.execution_result
                    st.markdown("---")
                    st.markdown("### Resultado")

                    # Metadata
                    col_m1, col_m2, col_m3 = st.columns(3)
                    col_m1.metric("Agente", result.get("agent_name", ""))
                    col_m2.metric("Version", f"v{result.get('version', 1)}")
                    col_m3.metric("Fecha", result.get("fecha", ""))

                    # Contenido del resultado
                    resultado_data = result.get("resultado", {})

                    if isinstance(resultado_data, dict) and "error" in resultado_data:
                        st.error(f"Error: {resultado_data['error']}")
                    elif isinstance(resultado_data, dict):
                        # Mostrar datos clave segun el tipo
                        if "dialogo" in resultado_data:
                            st.text_area(
                                "Dialogo Generado",
                                resultado_data["dialogo"],
                                height=300,
                                disabled=True,
                            )
                        elif "texto_completo" in resultado_data:
                            st.text_area(
                                "Transcripcion",
                                resultado_data["texto_completo"],
                                height=300,
                                disabled=True,
                            )
                        elif "reporte" in resultado_data:
                            st.code(resultado_data["reporte"], language=None)
                        elif "tendencia" in resultado_data:
                            st.metric("Tendencia", resultado_data["tendencia"])
                            st.metric("Puntaje Promedio", resultado_data.get("puntaje_promedio", "N/A"))
                            if resultado_data.get("puntos"):
                                import pandas as pd
                                df = pd.DataFrame(resultado_data["puntos"])
                                st.line_chart(df.set_index("fecha")["puntaje"])
                        elif "total_tareas" in resultado_data:
                            st.metric("Total Tareas", resultado_data["total_tareas"])
                            if resultado_data.get("agentes_activos"):
                                st.markdown("**Actividad por agente:**")
                                for ag, count in resultado_data["agentes_activos"].items():
                                    st.markdown(f"- {ag}: {count} tareas")
                        elif "evaluacion" in resultado_data:
                            puntaje = resultado_data.get("puntaje_total", "N/A")
                            st.metric("Puntaje Total", f"{puntaje}/100")
                            st.markdown(f"**Resumen:** {resultado_data.get('resumen_general', '')}")

                            if resultado_data.get("recomendaciones"):
                                st.markdown("**Recomendaciones:**")
                                for rec in resultado_data["recomendaciones"]:
                                    st.markdown(f"- {rec}")

                            with st.expander("Ver evaluacion completa (JSON)"):
                                st.json(resultado_data)
                        else:
                            st.json(resultado_data)

                        # Siempre mostrar JSON crudo en expander
                        if "dialogo" not in resultado_data and "texto_completo" not in resultado_data:
                            with st.expander("Ver datos crudos"):
                                st.json(resultado_data)
                    else:
                        st.write(resultado_data)

                    st.caption(
                        f"Guardado en: agent_results/{agent_id}/ | "
                        f"Timestamp: {result.get('timestamp', '')}"
                    )

    # ── Historial del agente seleccionado ──────────────────────────────
    st.markdown("---")
    st.markdown(f"### Historial de {agent['nombre']}")

    agent_history = load_all_results(agent_id)
    if agent_history:
        for record in agent_history[:10]:
            with st.expander(
                f"{record.get('skill_name', '?')} v{record.get('version', 1)} "
                f"- {record.get('fecha', '')} {record.get('hora', '')}"
            ):
                st.caption(f"Input: {record.get('input_summary', 'N/A')}")
                resultado = record.get("resultado", {})
                if isinstance(resultado, dict):
                    if "error" in resultado:
                        st.error(resultado["error"])
                    elif "puntaje_total" in resultado:
                        st.metric("Puntaje", f"{resultado['puntaje_total']}/100")
                    elif "texto_completo" in resultado:
                        st.text(resultado["texto_completo"][:500] + "...")
                    elif "dialogo" in resultado:
                        st.text(resultado["dialogo"][:500] + "...")
                    st.json(resultado)
                else:
                    st.write(resultado)
    else:
        st.caption("Este agente aun no ha ejecutado tareas.")
