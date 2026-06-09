"""
CLI para invocar agentes del call center directamente desde terminal.

Uso:
    python cli_agentes.py cortex ingesta_acd examples/acd_sample.csv
    python cli_agentes.py nexus calcular_staffing --texto "NdS: 80%" --previo agent_results/cortex/ingesta_acd_2026-06-09_v1.json
    python cli_agentes.py pipeline reporte_360_express examples/acd_sample.csv
    python cli_agentes.py pipeline ciclo_wfm_completo examples/acd_sample.csv --texto "NdS: 80%"
    python cli_agentes.py resultados                          # Ver todos los resultados
    python cli_agentes.py resultados cortex                   # Ver resultados de CORTEX
    python cli_agentes.py cadena examples/acd_sample.csv      # Cadena completa automática
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent_runner import execute_skill, load_all_results, _SafeEncoder
from pipeline_runner import execute_pipeline, PIPELINES
from agents_config import AGENTS


def _print_json(data, indent=2):
    print(json.dumps(data, indent=indent, cls=_SafeEncoder, ensure_ascii=False))


def cmd_skill(args, agent_id):
    """Ejecutar una skill de un agente."""
    skill_id = args.skill

    if agent_id not in AGENTS and agent_id != "modelos":
        print(f"Error: Agente '{agent_id}' no existe. Disponibles: {list(AGENTS.keys())}")
        sys.exit(1)

    file_bytes = None
    filename = ""
    if args.archivo:
        p = Path(args.archivo)
        if not p.exists():
            print(f"Error: Archivo '{args.archivo}' no encontrado")
            sys.exit(1)
        file_bytes = p.read_bytes()
        filename = p.name

    resultado_previo = None
    resultados_multiples = None

    if args.previo:
        with open(args.previo) as f:
            resultado_previo = json.load(f)

    if args.multiples:
        resultados_multiples = []
        for rpath in args.multiples:
            with open(rpath) as f:
                resultados_multiples.append(json.load(f))

    agent_cfg = AGENTS.get(agent_id, {})
    skill_name = skill_id
    for h in agent_cfg.get("habilidades", []):
        if h["id"] == skill_id:
            skill_name = h["nombre"]
            break

    print(f"\n{'='*60}")
    print(f"  Agente: {agent_id.upper()}")
    print(f"  Skill:  {skill_name} ({skill_id})")
    if filename:
        print(f"  Archivo: {filename}")
    if args.texto:
        print(f"  Texto:  {args.texto[:80]}...")
    print(f"{'='*60}\n")

    result = execute_skill(
        agent_id=agent_id,
        skill_id=skill_id,
        skill_name=skill_name,
        file_bytes=file_bytes,
        filename=filename,
        texto=args.texto or "",
        resultado_previo=resultado_previo,
        resultados_multiples=resultados_multiples,
    )

    if "error" in result.get("resultado", {}):
        print(f"ERROR: {result['resultado']['error']}")
        sys.exit(1)

    print("Resultado:")
    _print_json(result)
    print(f"\nGuardado en: agent_results/{agent_id}/")
    return result


def cmd_pipeline(args):
    """Ejecutar un pipeline predefinido."""
    pipeline_id = args.pipeline

    if pipeline_id not in PIPELINES:
        print(f"Error: Pipeline '{pipeline_id}' no existe.")
        print(f"Disponibles: {list(PIPELINES.keys())}")
        sys.exit(1)

    pipe = PIPELINES[pipeline_id]
    file_bytes = None
    filename = ""
    if args.archivo:
        p = Path(args.archivo)
        if not p.exists():
            print(f"Error: Archivo '{args.archivo}' no encontrado")
            sys.exit(1)
        file_bytes = p.read_bytes()
        filename = p.name

    print(f"\n{'='*60}")
    print(f"  Pipeline: {pipe['nombre']}")
    print(f"  Pasos:    {len(pipe['pasos'])}")
    if filename:
        print(f"  Archivo:  {filename}")
    print(f"{'='*60}\n")

    def status_cb(msg):
        print(f"  >> {msg}")

    results = execute_pipeline(
        pipeline_id=pipeline_id,
        file_bytes=file_bytes,
        filename=filename,
        texto=args.texto or "",
        status_callback=status_cb,
    )

    print(f"\n{'='*60}")
    print(f"  Pipeline completado: {len(results)} pasos ejecutados")
    print(f"{'='*60}\n")

    for i, r in enumerate(results):
        status = "OK" if "error" not in r.get("resultado", {}) else "ERROR"
        print(f"  Paso {i+1}: {r.get('skill_name', '?')} [{status}]")

    if results:
        print(f"\nUltimo resultado:")
        _print_json(results[-1])

    return results


def cmd_resultados(args):
    """Ver resultados guardados."""
    if args.agente:
        resultados = load_all_results(agent_id=args.agente)
        if not resultados:
            print(f"Sin resultados para '{args.agente}'")
            return
        print(f"\nResultados de {args.agente.upper()} ({len(resultados)}):\n")
        for r in resultados:
            ts = r.get("timestamp", "?")
            skill = r.get("skill_id", "?")
            ver = r.get("version", "?")
            inp = r.get("input_summary", "")[:50]
            print(f"  v{ver} | {ts} | {skill} | {inp}")
        return

    todos = load_all_results()
    por_agente = {}
    for r in todos:
        aid = r.get("agent_id", "desconocido")
        por_agente.setdefault(aid, []).append(r)

    print(f"\nResultados por agente:\n")
    for agent_id, resultados in sorted(por_agente.items()):
        print(f"  {agent_id.upper():12s} : {len(resultados)} resultados")
        for r in resultados[-3:]:
            skill = r.get("skill_id", "?")
            ts = r.get("timestamp", "?")[:10]
            print(f"    └─ {skill} ({ts})")


def cmd_cadena(args):
    """Ejecutar cadena completa: CORTEX → NEXUS → SENTINEL → ATLAS."""
    p = Path(args.archivo)
    if not p.exists():
        print(f"Error: Archivo '{args.archivo}' no encontrado")
        sys.exit(1)

    file_bytes = p.read_bytes()
    filename = p.name
    texto = args.texto or ""

    print(f"\n{'='*60}")
    print(f"  CADENA COMPLETA: {filename}")
    print(f"{'='*60}\n")

    # Paso 1: CORTEX ingesta
    print("  [1/4] CORTEX: Ingesta de datos...")
    ext = p.suffix.lower()
    if ext in (".mp3", ".wav", ".ogg", ".m4a"):
        cortex = execute_skill("cortex", "transcribir_audio", "Transcribir Audio",
                               audio_bytes=file_bytes, filename=filename)
    else:
        skill_id = "ingesta_acd"
        if "qa" in filename.lower():
            skill_id = "ingesta_qa"
        elif "cx" in filename.lower() or "csat" in filename.lower():
            skill_id = "ingesta_cx"
        elif "cubo" in filename.lower() or "trafico" in filename.lower():
            skill_id = "ingesta_cubo_trafico"
        elif "malla" in filename.lower():
            skill_id = "ingesta_malla"
        elif "gtr" in filename.lower():
            skill_id = "ingesta_gtr"
        elif "wfm" in filename.lower() or "metricas" in filename.lower():
            skill_id = "ingesta_wfm"

        cortex = execute_skill("cortex", skill_id, f"Ingesta {skill_id}",
                               file_bytes=file_bytes, filename=filename)
    print(f"    OK: {cortex.get('skill_name', '')}")

    # Paso 2: NEXUS cálculo
    print("  [2/4] NEXUS: Calculando staffing...")
    nexus = execute_skill("nexus", "calcular_carga_trabajo", "Carga de Trabajo",
                          resultado_previo=cortex)
    print(f"    OK: {nexus.get('skill_name', '')}")

    # Paso 3: NEXUS staffing Erlang
    print("  [3/4] NEXUS: Staffing Erlang C...")
    staffing = execute_skill("nexus", "calcular_staffing", "Staffing Erlang",
                             texto=texto or "NdS objetivo: 80%, Tiempo respuesta: 20s",
                             resultados_multiples=[cortex, nexus])
    print(f"    OK: {staffing.get('skill_name', '')}")

    # Paso 4: ATLAS informe
    print("  [4/4] ATLAS: Generando informe consolidado...")
    informe = execute_skill("atlas", "informe_consolidado", "Informe 360",
                            texto=texto or "Informe consolidado automatico",
                            resultados_multiples=[cortex, nexus, staffing])
    print(f"    OK: {informe.get('skill_name', '')}")

    print(f"\n{'='*60}")
    print(f"  CADENA COMPLETADA")
    print(f"{'='*60}\n")
    _print_json(informe)
    return informe


def cmd_listar(args):
    """Listar agentes, skills y pipelines disponibles."""
    print("\n AGENTES Y SKILLS DISPONIBLES\n")
    for agent_id, cfg in AGENTS.items():
        print(f"  {cfg['nombre']:12s} ({agent_id}) — {cfg['rol']}")
        for h in cfg.get("habilidades", []):
            acepta = []
            if h.get("acepta_archivo"):
                acepta.append("archivo")
            if h.get("acepta_texto"):
                acepta.append("texto")
            if h.get("acepta_resultado_previo"):
                acepta.append("previo")
            if h.get("multi_resultado"):
                acepta.append("multi")
            inputs = ", ".join(acepta) if acepta else "ninguno"
            print(f"    - {h['id']:30s} [{inputs}]")
        print()

    print("\n PIPELINES DISPONIBLES\n")
    for pid, pipe in PIPELINES.items():
        pasos = " → ".join(f"{p['agent_id'].upper()}/{p['skill_id']}" for p in pipe["pasos"])
        print(f"  {pid}")
        print(f"    {pipe['nombre']}: {pasos}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="CLI Multi-Agente Call Center",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python cli_agentes.py listar
  python cli_agentes.py cortex ingesta_acd examples/acd_sample.csv
  python cli_agentes.py nexus calcular_staffing --texto "NdS: 80%%" --previo agent_results/cortex/ingesta_acd_2026-06-09_v1.json
  python cli_agentes.py pipeline reporte_360_express examples/acd_sample.csv
  python cli_agentes.py cadena examples/acd_sample.csv --texto "meta NdS: 80%%"
  python cli_agentes.py resultados
  python cli_agentes.py resultados cortex
""",
    )
    sub = parser.add_subparsers(dest="comando")

    # Listar
    sub.add_parser("listar", help="Listar agentes, skills y pipelines")

    # Skill directo: agente skill [archivo]
    for agent_id in list(AGENTS.keys()):
        p = sub.add_parser(agent_id, help=f"Ejecutar skill de {agent_id.upper()}")
        p.add_argument("skill", help="ID de la skill a ejecutar")
        p.add_argument("archivo", nargs="?", help="Archivo de datos (opcional)")
        p.add_argument("--texto", "-t", default="", help="Texto/parámetros adicionales")
        p.add_argument("--previo", "-p", help="Ruta a resultado previo (JSON)")
        p.add_argument("--multiples", "-m", nargs="+", help="Rutas a múltiples resultados previos")

    # Pipeline
    p_pipe = sub.add_parser("pipeline", help="Ejecutar pipeline predefinido")
    p_pipe.add_argument("pipeline", help="ID del pipeline")
    p_pipe.add_argument("archivo", nargs="?", help="Archivo de datos")
    p_pipe.add_argument("--texto", "-t", default="", help="Texto/contexto adicional")

    # Resultados
    p_res = sub.add_parser("resultados", help="Ver resultados guardados")
    p_res.add_argument("agente", nargs="?", help="Filtrar por agente")

    # Cadena completa
    p_cad = sub.add_parser("cadena", help="Cadena completa automatica")
    p_cad.add_argument("archivo", help="Archivo de datos")
    p_cad.add_argument("--texto", "-t", default="", help="Contexto adicional")

    args = parser.parse_args()

    if not args.comando:
        parser.print_help()
        sys.exit(0)

    if args.comando == "listar":
        cmd_listar(args)
    elif args.comando == "pipeline":
        cmd_pipeline(args)
    elif args.comando == "resultados":
        cmd_resultados(args)
    elif args.comando == "cadena":
        cmd_cadena(args)
    else:
        cmd_skill(args, agent_id=args.comando)


if __name__ == "__main__":
    main()
