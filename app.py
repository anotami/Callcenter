"""
Streamlit UI - Equipo de Agentes de Call Center
MODELOS | CORTEX | NEXUS | SENTINEL | LEDGER | ATLAS
"""

import streamlit as st
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents_config import get_all_agents, get_skill
from agent_runner import (
    execute_skill, load_all_results, RESULTS_DIR,
    run_listar_modelos, run_probar_modelo, save_env_config, load_env_values,
)

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

    /* Forzar sidebar siempre visible */
    [data-testid="stSidebar"] {
        display: block !important;
        visibility: visible !important;
        position: relative !important;
        width: 21rem !important;
        min-width: 21rem !important;
        transform: none !important;
        z-index: 999;
    }
    [data-testid="stSidebar"] > div:first-child {
        width: 21rem !important;
        min-width: 21rem !important;
    }
    /* Ocultar boton de colapsar ya que siempre esta visible */
    [data-testid="collapsedControl"] { display: none !important; }
    button[kind="headerNoPadding"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── Estado ─────────────────────────────────────────────────────────────

if "selected_agent" not in st.session_state:
    st.session_state.selected_agent = None
if "selected_skill" not in st.session_state:
    st.session_state.selected_skill = None
if "execution_result" not in st.session_state:
    st.session_state.execution_result = None
if "selected_model" not in st.session_state:
    from config import LLM_MODEL
    st.session_state.selected_model = LLM_MODEL

AGENTS = get_all_agents()

AGENT_ICONS = {
    "modelos": ":material/memory:",
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

    # Mostrar solo agentes operativos (excluir modelos)
    operational_agents = {k: v for k, v in AGENTS.items() if k != "modelos"}
    cols = st.columns(len(operational_agents))
    for i, (agent_id, agent) in enumerate(operational_agents.items()):
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

elif st.session_state.selected_agent == "modelos":
    # ── Vista especial: MODELOS ────────────────────────────────────────
    agent = AGENTS["modelos"]
    st.markdown(f"# {agent['nombre']}")
    st.markdown(f'<span class="agent-role">{agent["rol"]}</span>', unsafe_allow_html=True)
    st.markdown(agent["descripcion"])
    st.markdown("---")

    import config as _cfg

    # ── Proveedor ─────────────────────────────────────────────────────
    PROVEEDORES = {
        "Ollama (Local)": {
            "url": "http://localhost:11434/v1",
            "api_key": "not-needed",
            "ayuda": "Instalar: `curl -fsSL https://ollama.ai/install.sh | sh` → luego `ollama pull llama3.2:3b`",
            "necesita_key": False,
        },
        "LM Studio (Local)": {
            "url": "http://localhost:1234/v1",
            "api_key": "not-needed",
            "ayuda": "Descargar LM Studio, cargar un modelo y activar el servidor local.",
            "necesita_key": False,
        },
        "Groq Cloud": {
            "url": "https://api.groq.com/openai/v1",
            "api_key": "",
            "ayuda": "Obtener API key gratis en: https://console.groq.com/keys",
            "necesita_key": True,
        },
        "OpenAI": {
            "url": "https://api.openai.com/v1",
            "api_key": "",
            "ayuda": "Obtener API key en: https://platform.openai.com/api-keys",
            "necesita_key": True,
        },
        "Personalizado": {
            "url": "",
            "api_key": "",
            "ayuda": "Cualquier servidor compatible con la API de OpenAI.",
            "necesita_key": True,
        },
    }

    # Detectar proveedor actual
    current_url = _cfg.LLM_BASE_URL
    detected_provider = "Personalizado"
    for nombre, datos in PROVEEDORES.items():
        if datos["url"] and datos["url"] in current_url:
            detected_provider = nombre
            break

    if "_provider" not in st.session_state:
        st.session_state["_provider"] = detected_provider

    # ══════════════════════════════════════════════════════════════════
    #  SECCION 1: Configuracion del Proveedor LLM
    # ══════════════════════════════════════════════════════════════════
    st.markdown("### 1. Proveedor LLM")

    provider = st.selectbox(
        "Selecciona tu proveedor de modelos:",
        list(PROVEEDORES.keys()),
        index=list(PROVEEDORES.keys()).index(st.session_state["_provider"]),
        key="_sel_provider",
    )
    st.session_state["_provider"] = provider
    prov_data = PROVEEDORES[provider]

    st.info(prov_data["ayuda"])

    col_url, col_key = st.columns(2)
    with col_url:
        default_url = prov_data["url"] if prov_data["url"] else current_url
        new_base_url = st.text_input(
            "URL del servidor",
            value=default_url,
            key="_cfg_llm_url",
            disabled=(provider not in ("Personalizado",)),
            help="Endpoint compatible con OpenAI API",
        )
    with col_key:
        default_key = _cfg.LLM_API_KEY if _cfg.LLM_API_KEY != "not-needed" else ""
        if not prov_data["necesita_key"]:
            st.text_input(
                "API Key",
                value="No requerida",
                disabled=True,
                key="_cfg_key_disabled",
            )
            new_api_key = "not-needed"
        else:
            new_api_key = st.text_input(
                "API Key",
                value=default_key,
                type="password",
                key="_cfg_llm_key",
                placeholder="Pega tu API key aqui...",
            )

    col_model, col_fallback = st.columns(2)
    with col_model:
        new_llm_model = st.text_input(
            "Modelo principal",
            value=_cfg.LLM_MODEL,
            key="_cfg_llm_model",
            help="Se puede cambiar despues al detectar los modelos disponibles",
        )
    with col_fallback:
        new_fallback = st.text_input(
            "Modelos fallback (separados por coma)",
            value=",".join(_cfg.LLM_FALLBACK_MODELS),
            key="_cfg_llm_fallback",
            help="Modelos alternativos si el principal no responde",
        )

    # ── Groq Cloud como fallback adicional ────────────────────────────
    st.markdown("---")
    st.markdown("### Groq Cloud (Fallback opcional)")
    st.caption("Si usas un servidor local, Groq puede ser tu respaldo en la nube cuando no responda.")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        new_groq_key = st.text_input(
            "Groq API Key",
            value=_cfg.GROQ_API_KEY,
            type="password",
            key="_cfg_groq_key",
            help="Obtener gratis en https://console.groq.com/keys — dejar vacio para desactivar",
        )
    with col_g2:
        st.text_input("Groq URL", value=_cfg.GROQ_BASE_URL, disabled=True, key="_cfg_groq_url")

    # ── Whisper ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Whisper (Transcripcion de Audio)")
    st.caption("Motor de transcripcion de audio a texto. Modelos mas grandes = mejor calidad pero mas lento.")
    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1:
        whisper_opts = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
        new_whisper_model = st.selectbox(
            "Modelo Whisper",
            whisper_opts,
            index=whisper_opts.index(_cfg.WHISPER_MODEL) if _cfg.WHISPER_MODEL in whisper_opts else 5,
            key="_cfg_whisper_model",
        )
    with col_w2:
        new_whisper_device = st.selectbox(
            "Dispositivo",
            ["cuda", "cpu"],
            index=0 if _cfg.WHISPER_DEVICE == "cuda" else 1,
            key="_cfg_whisper_device",
            help="cuda = GPU (rapido) | cpu = procesador (lento)",
        )
    with col_w3:
        new_whisper_lang = st.text_input(
            "Idioma",
            value=_cfg.WHISPER_LANGUAGE,
            key="_cfg_whisper_lang",
            help="Codigo ISO: es (espanol), en (ingles), pt (portugues), etc.",
        )

    # ── HuggingFace ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### HuggingFace (Diarizacion de Hablantes)")
    st.caption("Token necesario para pyannote (identificar quien habla en cada segmento del audio).")
    new_hf_token = st.text_input(
        "HuggingFace Token",
        value=_cfg.HF_TOKEN,
        type="password",
        key="_cfg_hf_token",
        help="Obtener en https://huggingface.co/settings/tokens — Aceptar licencia en https://huggingface.co/pyannote/speaker-diarization-3.1",
    )

    # ── SQL Server ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Base de Datos (SQL Server)")
    st.caption("Conexion opcional para almacenar resultados en base de datos.")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        new_sql_server = st.text_input("Servidor", value=_cfg.SQL_SERVER, key="_cfg_sql_server")
        new_sql_db = st.text_input("Base de datos", value=_cfg.SQL_DATABASE, key="_cfg_sql_db")
        new_sql_driver = st.text_input("Driver ODBC", value=_cfg.SQL_DRIVER, key="_cfg_sql_driver")
    with col_s2:
        new_sql_user = st.text_input("Usuario", value=_cfg.SQL_USERNAME, key="_cfg_sql_user")
        new_sql_pass = st.text_input("Password", value=_cfg.SQL_PASSWORD, key="_cfg_sql_pass", type="password")

    # ── Boton Guardar ─────────────────────────────────────────────────
    st.markdown("---")
    if st.button("Guardar toda la Configuracion", use_container_width=True, type="primary",
                  icon=":material/save:"):
        # Usar URL del proveedor si no es personalizado
        save_url = prov_data["url"] if prov_data["url"] else new_base_url
        changes = {
            "LLM_BASE_URL": save_url,
            "LLM_MODEL": new_llm_model,
            "LLM_API_KEY": new_api_key,
            "LLM_FALLBACK_MODELS": new_fallback,
            "GROQ_API_KEY": new_groq_key,
            "WHISPER_MODEL": new_whisper_model,
            "WHISPER_DEVICE": new_whisper_device,
            "WHISPER_LANGUAGE": new_whisper_lang,
            "HF_TOKEN": new_hf_token,
            "SQL_SERVER": new_sql_server,
            "SQL_DATABASE": new_sql_db,
            "SQL_USERNAME": new_sql_user,
            "SQL_PASSWORD": new_sql_pass,
            "SQL_DRIVER": new_sql_driver,
        }
        save_env_config(changes)
        _cfg.LLM_FALLBACK_MODELS = [m.strip() for m in new_fallback.split(",") if m.strip()]
        st.session_state.selected_model = new_llm_model
        # Limpiar estado de deteccion previo
        st.session_state.pop("_modelos_info", None)
        st.session_state.pop("_test_result", None)
        st.success("Configuracion guardada en `.env` y aplicada.")
        st.rerun()

    # ══════════════════════════════════════════════════════════════════
    #  SECCION 3: Conectar y Detectar Modelos
    # ══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 2. Conectar y Detectar Modelos")
    st.caption(f"Servidor actual: `{_cfg.LLM_BASE_URL}` | Modelo: `{_cfg.LLM_MODEL}`")

    col_detect, col_status = st.columns([1, 2])

    with col_detect:
        if st.button("Detectar Modelos", use_container_width=True, type="primary",
                      icon=":material/refresh:", key="_btn_detectar"):
            with st.spinner("Conectando..."):
                info = run_listar_modelos()
                st.session_state["_modelos_info"] = info

    info = st.session_state.get("_modelos_info")

    with col_status:
        if info is None:
            st.caption("Presiona 'Detectar Modelos' para verificar la conexion.")
        elif info["conectado"]:
            st.success(f"Conectado — {info['total']} modelo(s)")
        else:
            error_msg = info.get("error", "Error desconocido")
            if "401" in error_msg or "api_key" in error_msg.lower():
                st.error("API Key invalida. Revisa la key en la configuracion arriba y guarda.")
            elif "Connection" in error_msg or "refused" in error_msg.lower():
                st.error("No se pudo conectar al servidor. Verifica que este corriendo.")
            else:
                st.error(f"Error: {error_msg}")

    if info and info["conectado"] and info["modelos"]:
        modelos = info["modelos"]

        st.markdown("**Modelos disponibles en el servidor:**")
        current = st.session_state.selected_model
        idx = modelos.index(current) if current in modelos else 0

        chosen = st.radio(
            "Selecciona el modelo que usaran los agentes:",
            modelos,
            index=idx,
            key="_radio_modelo",
        )
        if chosen != st.session_state.selected_model:
            st.session_state.selected_model = chosen
            _cfg.LLM_MODEL = chosen
            save_env_config({"LLM_MODEL": chosen})
            st.rerun()

        st.info(f"Modelo activo: **{st.session_state.selected_model}**")

    # ══════════════════════════════════════════════════════════════════
    #  SECCION 4: Probar Modelo
    # ══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 3. Probar Modelo")

    modelos_disponibles = info["modelos"] if info and info.get("conectado") else []

    if not modelos_disponibles:
        st.caption("Primero conecta y detecta los modelos disponibles arriba.")
    else:
        col_t1, col_t2 = st.columns([1, 2])
        with col_t1:
            modelo_test = st.selectbox(
                "Modelo:",
                modelos_disponibles,
                key="_select_test_modelo",
            )
            if st.button(f"Probar", use_container_width=True,
                          icon=":material/play_arrow:", key="_btn_probar"):
                with st.spinner(f"Probando {modelo_test}..."):
                    test_result = run_probar_modelo(modelo_test)
                    st.session_state["_test_result"] = test_result

        with col_t2:
            test_result = st.session_state.get("_test_result")
            if test_result:
                if test_result["ok"]:
                    st.success(f"**{test_result['modelo']}** respondio en **{test_result['tiempo_seg']}s**")
                    st.markdown(f"> {test_result['respuesta']}")
                else:
                    st.error(f"**{test_result['modelo']}** fallo: {test_result['error']}")
            else:
                st.caption("Selecciona un modelo y presiona 'Probar'.")

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
