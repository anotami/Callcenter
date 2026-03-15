"""
Streamlit UI - Equipo de Agentes de Call Center
CORTEX | NEXUS | SENTINEL | LEDGER | ATLAS
"""

import streamlit as st
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents_config import get_all_agents, get_skill
from agent_runner import execute_skill, load_all_results, RESULTS_DIR

# ── Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CallCenter AI Team",
    layout="wide",
    page_icon=":headphones:",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .agent-role { font-size: 0.75em; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    #MainMenu {visibility: hidden;}
    header[data-testid="stHeader"] {visibility: hidden;}
    [data-testid="collapsedControl"] {visibility: visible !important;}
</style>
""", unsafe_allow_html=True)

# ── Estado ─────────────────────────────────────────────────────────────

if "selected_agent" not in st.session_state:
    st.session_state.selected_agent = None
if "selected_skill" not in st.session_state:
    st.session_state.selected_skill = None
if "execution_result" not in st.session_state:
    st.session_state.execution_result = None

AGENTS = get_all_agents()

AGENT_ICONS = {
    "cortex": ":material/database:",
    "nexus": ":material/calculate:",
    "sentinel": ":material/verified_user:",
    "ledger": ":material/payments:",
    "atlas": ":material/analytics:",
}

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"}

# ── Sidebar ────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Equipo de Agentes")
    st.caption("Selecciona un agente para ver sus habilidades")
    st.divider()

    for agent_id, agent in AGENTS.items():
        icon = AGENT_ICONS.get(agent_id, ":material/smart_toy:")
        is_selected = st.session_state.selected_agent == agent_id

        if st.button(
            f"{agent['nombre']} — {agent['rol']}",
            key=f"agent_{agent_id}",
            use_container_width=True,
            icon=icon,
            type="primary" if is_selected else "secondary",
        ):
            st.session_state.selected_agent = agent_id
            st.session_state.selected_skill = None
            st.session_state.execution_result = None
            st.rerun()

    # Historial rapido
    st.divider()
    st.markdown("### Historial Reciente")
    all_results = load_all_results()
    if all_results:
        for r in all_results[:8]:
            st.caption(
                f"{r.get('agent_name', '?')} / {r.get('skill_name', '?')} "
                f"v{r.get('version', 1)} - {r.get('fecha', '')}"
            )
    else:
        st.caption("Sin resultados aun.")

# ── Panel Principal ────────────────────────────────────────────────────

if st.session_state.selected_agent is None:
    st.markdown("# CallCenter AI Team")
    st.markdown("### Tu equipo de agentes inteligentes para operaciones de call center")
    st.markdown("---")

    cols = st.columns(len(AGENTS))
    for i, (agent_id, agent) in enumerate(AGENTS.items()):
        with cols[i]:
            st.markdown(f"#### {agent['nombre']}")
            st.markdown(f'<span class="agent-role">{agent["rol"]}</span>', unsafe_allow_html=True)
            st.markdown(agent["descripcion"][:120] + "...")
            st.metric("Habilidades", len(agent["habilidades"]))

    st.markdown("---")
    st.info("Selecciona un agente en el panel lateral para ver sus habilidades y ejecutarlas.")

    if all_results:
        st.markdown("### Actividad del Equipo")
        ca, cb, cc = st.columns(3)
        ca.metric("Total Tareas", len(all_results))
        cb.metric("Agentes Activos", len(set(r.get("agent_id") for r in all_results)))
        cc.metric("Dias con Actividad", len(set(r.get("fecha") for r in all_results)))

else:
    # ── Vista de Agente ────────────────────────────────────────────────
    agent_id = st.session_state.selected_agent
    agent = AGENTS[agent_id]

    st.markdown(f"# {agent['nombre']}")
    st.markdown(f'<span class="agent-role">{agent["rol"]}</span>', unsafe_allow_html=True)
    st.markdown(agent["descripcion"])
    st.markdown("---")

    col_skills, col_exec = st.columns([1, 2])

    # ── Lista de Habilidades ───────────────────────────────────────────
    with col_skills:
        st.markdown("### Habilidades")
        for skill in agent["habilidades"]:
            is_sel = st.session_state.selected_skill == skill["id"]
            if st.button(
                skill["nombre"],
                key=f"skill_{skill['id']}",
                use_container_width=True,
                type="primary" if is_sel else "secondary",
            ):
                st.session_state.selected_skill = skill["id"]
                st.session_state.execution_result = None
                st.rerun()
            st.caption(skill["descripcion"][:90])
            st.markdown("")

    # ── Panel de Ejecucion ─────────────────────────────────────────────
    with col_exec:
        if st.session_state.selected_skill is None:
            st.info("Selecciona una habilidad a la izquierda para ver detalles y ejecutarla.")
        else:
            skill = get_skill(agent_id, st.session_state.selected_skill)
            if not skill:
                st.error("Habilidad no encontrada")
            else:
                st.markdown(f"### {skill['nombre']}")
                st.markdown(skill["descripcion"])

                st.markdown("**Datos necesarios:**")
                for d in skill["datos_necesarios"]:
                    st.markdown(f"- `{d}`")
                st.markdown(f"**Resultado:** {skill['resultado']}")
                st.markdown("---")
                st.markdown("### Ejecutar")

                # ── Inputs ─────────────────────────────────────────────
                uploaded_file = None
                input_text = ""
                selected_prev_results = []

                if skill.get("acepta_archivo"):
                    exts = skill.get("extensiones", [])
                    uploaded_file = st.file_uploader(
                        f"Archivo ({', '.join(exts)})",
                        type=[e.lstrip(".") for e in exts],
                        key=f"upload_{skill['id']}",
                    )

                if skill.get("acepta_texto"):
                    input_text = st.text_area(
                        "Texto / Parametros",
                        height=120,
                        placeholder="Pega texto, dialogo o parametros aqui...",
                        key=f"text_{skill['id']}",
                    )

                if skill.get("acepta_resultado_previo"):
                    compatible = skill.get("agentes_compatibles", [])
                    is_multi = skill.get("multi_resultado", False)

                    prev_results = []
                    for ca in compatible:
                        prev_results.extend(load_all_results(ca))
                    if skill["id"] == "resumen_equipo":
                        prev_results = load_all_results()

                    if prev_results:
                        st.markdown("**Resultados previos disponibles:**")
                        options = [
                            f"{r.get('agent_name', '?')} / {r.get('skill_name', '?')} "
                            f"v{r.get('version', 1)} - {r.get('fecha', '')}"
                            for r in prev_results
                        ]
                        if is_multi:
                            sel_idx = st.multiselect(
                                "Selecciona resultados (2+ para analisis)",
                                range(len(options)),
                                format_func=lambda i: options[i],
                                key=f"multi_{skill['id']}",
                            )
                            selected_prev_results = [prev_results[i] for i in sel_idx]
                        else:
                            sel_idx = st.selectbox(
                                "Selecciona resultado previo",
                                range(len(options)),
                                format_func=lambda i: options[i],
                                key=f"single_{skill['id']}",
                            )
                            if sel_idx is not None:
                                selected_prev_results = [prev_results[sel_idx]]
                    else:
                        st.caption("No hay resultados previos. Ejecuta primero una habilidad compatible.")

                # ── Boton Ejecutar ─────────────────────────────────────
                st.markdown("")
                can_exec = (
                    uploaded_file is not None
                    or len(input_text.strip()) > 0
                    or len(selected_prev_results) > 0
                )

                if st.button(
                    f"Ejecutar: {skill['nombre']}",
                    disabled=not can_exec,
                    use_container_width=True,
                    type="primary",
                    key=f"exec_{skill['id']}",
                ):
                    with st.status(
                        f"Ejecutando {skill['nombre']}...",
                        expanded=True,
                    ) as status_ui:
                        audio_bytes = None
                        file_bytes = None
                        filename = ""

                        if uploaded_file:
                            raw = uploaded_file.read()
                            filename = uploaded_file.name
                            ext = Path(filename).suffix.lower()
                            if ext in AUDIO_EXTENSIONS:
                                audio_bytes = raw
                            else:
                                file_bytes = raw

                        resultado_previo = None
                        if selected_prev_results and not skill.get("multi_resultado"):
                            resultado_previo = selected_prev_results[0].get("resultado")

                        result = execute_skill(
                            agent_id=agent_id,
                            skill_id=skill["id"],
                            skill_name=skill["nombre"],
                            audio_bytes=audio_bytes,
                            file_bytes=file_bytes,
                            filename=filename,
                            texto=input_text,
                            resultado_previo=resultado_previo,
                            resultados_multiples=(
                                selected_prev_results if skill.get("multi_resultado") else None
                            ),
                            status_container=status_ui,
                        )
                        st.session_state.execution_result = result
                        res_data = result.get("resultado", {})
                        if isinstance(res_data, dict) and "error" in res_data:
                            status_ui.update(
                                label=f"Error: {res_data['error'][:80]}",
                                state="error",
                            )
                        else:
                            modelo = ""
                            if isinstance(res_data, dict):
                                modelo = res_data.get("_modelo_usado", "")
                            label = f"{skill['nombre']} completado"
                            if modelo:
                                label += f" (modelo: {modelo})"
                            status_ui.update(label=label, state="complete")

                # ── Mostrar Resultado ──────────────────────────────────
                if st.session_state.execution_result:
                    result = st.session_state.execution_result
                    st.markdown("---")
                    st.markdown("### Resultado")

                    cm1, cm2, cm3 = st.columns(3)
                    cm1.metric("Agente", result.get("agent_name", ""))
                    cm2.metric("Version", f"v{result.get('version', 1)}")
                    cm3.metric("Fecha", result.get("fecha", ""))

                    data = result.get("resultado", {})

                    if isinstance(data, dict) and "error" in data:
                        st.error(f"Error: {data['error']}")

                    elif isinstance(data, dict):
                        # Render inteligente segun tipo de resultado
                        if "dialogo" in data:
                            st.text_area("Dialogo", data["dialogo"], height=300, disabled=True)
                        elif "texto_completo" in data:
                            st.text_area("Transcripcion", data["texto_completo"], height=300, disabled=True)
                        elif "reporte" in data:
                            st.code(data["reporte"], language=None)
                        elif "evaluacion" in data:
                            st.metric("Puntaje Total", f"{data.get('puntaje_total', 'N/A')}/100")
                            st.markdown(f"**Resumen:** {data.get('resumen_general', '')}")
                            if data.get("recomendaciones"):
                                st.markdown("**Recomendaciones:**")
                                for rec in data["recomendaciones"]:
                                    st.markdown(f"- {rec}")
                        elif "kpis" in data or "kpis_semana" in data or "kpis_mes" in data:
                            kpis = data.get("kpis") or data.get("kpis_semana") or data.get("kpis_mes", [])
                            if kpis:
                                import pandas as pd
                                st.dataframe(pd.DataFrame(kpis), use_container_width=True)
                            if data.get("resumen_ejecutivo"):
                                st.markdown(f"**Resumen:** {data['resumen_ejecutivo']}")
                            if data.get("alertas"):
                                st.warning("**Alertas:** " + " | ".join(str(a) for a in data["alertas"]))
                        elif "resultado" in data and "agentes_minimos" in data.get("resultado", {}):
                            # Staffing
                            r = data["resultado"]
                            sc1, sc2, sc3 = st.columns(3)
                            sc1.metric("Agentes Minimos", r["agentes_minimos"])
                            sc2.metric("Con Shrinkage", r["agentes_con_shrinkage"])
                            sc3.metric("NdS Proyectado", f"{r['nivel_servicio_proyectado']}%")
                            st.metric("Ocupacion", f"{r['ocupacion_pct']}%")
                        elif "total_tareas" in data:
                            st.metric("Total Tareas", data["total_tareas"])
                            if data.get("agentes_activos"):
                                for ag, cnt in data["agentes_activos"].items():
                                    st.markdown(f"- **{ag}**: {cnt} tareas")
                        elif "errores_criticos" in data:
                            st.metric("Riesgo General", data.get("riesgo_general", "?"))
                            st.metric("Errores Detectados", data.get("total_errores", 0))
                            for err in data.get("errores_criticos", []):
                                sev = err.get("severidad", "?")
                                color = "red" if sev == "alta" else "orange" if sev == "media" else "blue"
                                st.markdown(f"- :{color}[**{sev.upper()}**] {err.get('tipo', '')}: {err.get('descripcion', '')}")
                        elif "lineas" in data:
                            # Facturacion
                            import pandas as pd
                            st.dataframe(pd.DataFrame(data["lineas"]), use_container_width=True)
                            st.metric("Total Facturacion", data.get("total_facturacion", "N/A"))
                        elif "tendencia" in data:
                            st.metric("Tendencia", data["tendencia"])
                            st.metric("Promedio", data.get("puntaje_promedio", "N/A"))
                        else:
                            st.json(data)

                        with st.expander("Ver JSON completo"):
                            st.json(data)
                    else:
                        st.write(data)

                    st.caption(
                        f"Guardado en: agent_results/{agent_id}/ | "
                        f"Timestamp: {result.get('timestamp', '')}"
                    )

    # ── Historial del agente ───────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"### Historial de {agent['nombre']}")

    agent_history = load_all_results(agent_id)
    if agent_history:
        for rec in agent_history[:10]:
            with st.expander(
                f"{rec.get('skill_name', '?')} v{rec.get('version', 1)} "
                f"- {rec.get('fecha', '')} {rec.get('hora', '')}"
            ):
                st.caption(f"Input: {rec.get('input_summary', 'N/A')}")
                res = rec.get("resultado", {})
                if isinstance(res, dict):
                    if "error" in res:
                        st.error(res["error"])
                    elif "puntaje_total" in res:
                        st.metric("Puntaje", f"{res['puntaje_total']}/100")
                    st.json(res)
                else:
                    st.write(res)
    else:
        st.caption("Este agente aun no ha ejecutado tareas.")
