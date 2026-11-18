from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .models import Settings
from . import service

DEFAULT_GOLD = "samples/gold/questions.jsonl"
ADVERSARIAL_GOLD = "samples/gold/adversarial.jsonl"
DEFAULT_PORT = 8020


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="knowledge-ops",
        description="Knowledge Ops Console: ingesta, índice léxico, respuestas con citas y evaluación.",
    )
    p.add_argument("--home", help="directorio de trabajo para data/ y results/ (env KNOPS_HOME)")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest", help="ingesta de documentos .txt/.md y reconstrucción del índice")
    ing.add_argument("dir", help="directorio con documentos")

    ask = sub.add_parser("ask", help="pregunta con citas; abstiene si la evidencia es débil")
    ask.add_argument("question")
    ask.add_argument("-k", type=int, default=4)
    ask.add_argument("--json", action="store_true", dest="as_json")

    ev = sub.add_parser("eval", help="evalúa contra el gold set y escribe results/eval.md y .json")
    ev.add_argument("--gold", action="append", help=f"gold set (repetible; por defecto {DEFAULT_GOLD})")
    ev.add_argument("--all", action="store_true", help="evalúa el gold principal y el adversarial por separado")
    ev.add_argument("-k", type=int, default=4)

    srv = sub.add_parser("serve", help="UI web local")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=DEFAULT_PORT)

    sub.add_parser("status", help="estado del índice, consultas y evaluaciones")
    return p


def _print_answer(ans: dict) -> None:
    flag = "ABSTENCIÓN" if ans["abstained"] else "RESPUESTA"
    print(f"[{flag}] confianza={ans['confidence']:.2f}")
    print(ans["answer"])
    if ans["reason"]:
        print(f"motivo: {ans['reason']}")
    for c in ans["citations"]:
        sec = f" · {c['section']}" if c["section"] else ""
        print(f"  [{c['n']}] {c['doc']}{sec} (score {c['score']:.2f})")


def cmd_status(settings: Settings) -> int:
    st = service.status(settings)
    print(f"home: {st['root']}")
    if st["index"]:
        i = st["index"]
        print(f"índice: {i['docs']} docs · {i['chunks']} chunks · {i['terms']} términos · {i['built_at']}")
    else:
        print("índice: no construido (ejecute `ingest <dir>`)")
    c = st["counts"]
    print(f"ingestas={c['ingest_runs']} consultas={c['queries']} evaluaciones={c['eval_runs']}")
    if st["last_eval"]:
        m = st["last_eval"]["metrics"]
        print(f"última eval: pass_rate={m['pass_rate']:.0%} abstención={m['abstention_correct']:.0%}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    settings = Settings.from_env(args.home)

    try:
        if args.cmd == "ingest":
            r = service.run_ingest(settings, args.dir)
            print(f"ingesta #{r['run_id']}: {r['docs']} docs · {r['chunks']} chunks · {r['terms']} términos")
            if r["skipped"]:
                print(f"omitidos: {', '.join(r['skipped'])}")
            print(f"índice: {settings.index_path}")
            return 0
        if args.cmd == "ask":
            ans = service.run_ask(settings, args.question, k=args.k).to_dict()
            if args.as_json:
                print(json.dumps(ans, ensure_ascii=False, indent=2))
            else:
                _print_answer(ans)
            return 0
        if args.cmd == "eval":
            golds = list(args.gold or [])
            if args.all:
                golds += [g for g in (DEFAULT_GOLD, ADVERSARIAL_GOLD) if g not in golds]
            golds = golds or [DEFAULT_GOLD]
            # El gold principal va al final para que `status` siga mostrando su pass rate.
            golds.sort(key=lambda g: Path(g).stem == service.MAIN_GOLD_STEM)
            exit_code = 0
            for gold in golds:
                report = service.run_eval_suite(settings, Path(gold), k=args.k)
                m = report["metrics"]
                retrieval = ""
                if m["answerable"]:
                    recall = m[f"recall@{m['k']}"]
                    retrieval = f"recall@{m['k']}={recall:.0%} citation_hit={m['citation_hit']:.0%} "
                print(
                    f"[{Path(gold).stem}] casos={m['cases']} {retrieval}"
                    f"abstención={m['abstention_correct']:.0%} pass={m['pass_rate']:.0%}"
                )
                print(f"reportes: {report['outputs']['md']} · {report['outputs']['json']}")
                if m["pass_rate"] != 1.0:
                    exit_code = 1
            return exit_code
        if args.cmd == "serve":
            import uvicorn
            from .web import create_app

            uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level="info")
            return 0
        if args.cmd == "status":
            return cmd_status(settings)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
