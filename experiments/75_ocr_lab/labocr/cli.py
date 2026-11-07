"""labocr CLI:  python -m labocr <command>   (run from experiments/75_ocr_lab, the repo's .venv)

  doctor                       prerequisites (no downloads, no paid calls)
  ingest FILE --dataset D --document-id ID --pages 1,2 --category C   immutable copy + manifest entries
  render --dataset D [--dpi 300]                                       canonical renders for a dataset's pages
  run --dataset D --engine E --variant V --worker-json ARGV [--settings JSON] [--embed-image] [--fixture]
  run --resume RUN_ID
  status RUN_ID
  evaluate --dataset D --page PAGE_ID [--revision REV]               score every run against the owner's latest
                                                                       (or named) correction -> out/data/scores/
  compare --dataset D --page PAGE_ID                                   the page bundle the /lab page reads
                                                                       (engines, texts, boxes, disagreements)
  renormalise RUN_ID                                                   rebuild blocks from stored raw replies
Worker argv is a JSON list (never a shell string).  The data root defaults to out/data (--root).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = HERE / "out" / "data"


def cmd_doctor(a):
    import importlib
    rep = {}
    for m in ("pydantic", "pypdfium2", "cv2", "numpy", "rapidfuzz", "lxml", "yaml"):
        try:
            mod = importlib.import_module(m)
            rep[m] = getattr(mod, "__version__", "ok")
        except Exception as e:  # noqa: BLE001
            rep[m] = f"MISSING: {e}"
    try:
        from pypdfium2.version import PDFIUM_INFO, PYPDFIUM_INFO
        rep["pypdfium2"] = f"{PYPDFIUM_INFO} / pdfium {PDFIUM_INFO}"
        rep["pypdfium2_pin_ok"] = str(PYPDFIUM_INFO) == "5.12.1"
    except Exception as e:  # noqa: BLE001
        rep["pypdfium2_pin_ok"] = f"unknown: {e}"
    try:
        import inkscript.gold.text  # noqa: F401
        rep["inkscript.gold.text"] = "ok"
    except Exception as e:  # noqa: BLE001
        rep["inkscript.gold.text"] = f"MISSING: {e}"
    root = Path(a.root)
    rep["data_root"] = str(root)
    rep["data_root_free_gb"] = round(shutil.disk_usage(root if root.exists() else HERE).free / 1e9, 1)
    rep["vastai_cli"] = str(Path.home() / ".local/venvs/vast/bin/vastai") if (Path.home() / ".local/venvs/vast/bin/vastai").exists() else "absent"
    rep["ssh_key_vast"] = (Path.home() / ".ssh/id_ed25519_vast").exists()
    rep["nvidia_smi_local"] = shutil.which("nvidia-smi") is not None
    rep["note"] = "GPU engines run in their own envs on a rented host (workers/setup_gpu.sh); nothing is downloaded here"
    print(json.dumps(rep, indent=1, ensure_ascii=False))


def cmd_ingest(a):
    from . import ingest as I
    from .schemas import ManifestEntry
    root = Path(a.root)
    src = I.ingest_source(Path(a.file), root)
    pages = [int(x) for x in a.pages.split(",")] if a.pages else list(range(1, src.page_count + 1))
    entries = {e.page_id: e for e in (I.read_manifest(root, a.dataset) if I.manifest_path(root, a.dataset).exists() else [])}
    for p in pages:
        pid = I.page_id_of(a.document_id, p)
        nat = I.native_text(src, root, p)
        entries[pid] = ManifestEntry(dataset=a.dataset, document_id=a.document_id, page_id=pid, page_number=p,
                                     source_id=src.source_id, category=a.category, languages=a.languages.split(","),
                                     provenance=a.provenance, usage=a.usage, split=a.split,
                                     native_text=nat.model_copy(update={"text": None}))
    leak = I.check_leakage(list(entries.values()))
    if leak:
        raise SystemExit(f"split leakage: {leak}")
    h = I.write_manifest(root, a.dataset, list(entries.values()))
    print(json.dumps(dict(source=src.model_dump(), pages=pages, manifest_hash=h), indent=1, ensure_ascii=False))


def cmd_render(a):
    from . import ingest as I
    root = Path(a.root)
    out = []
    entries = I.read_manifest(root, a.dataset)
    for e in entries:
        src = I.source_by_id(root, e.source_id)
        rr = I.render_page(src, root, e.page_number, dpi=a.dpi, grey=not a.rgb)
        e.render_id = rr.render_id
        out.append(rr.model_dump())
    h = I.write_manifest(root, a.dataset, entries)
    print(json.dumps(dict(renders=out, manifest_hash=h), indent=1))


def cmd_run(a):
    from . import runs as R
    from .schemas import EngineConfig
    root = Path(a.root)
    if a.resume:
        rid = a.resume
    else:
        argv = json.loads(a.worker_json)
        cfg = EngineConfig(engine=a.engine, variant=a.variant, settings=json.loads(a.settings or "{}"),
                           model_revision=a.revision)
        rid = R.create_run(root, a.dataset, cfg, argv, pages=a.pages.split(",") if a.pages else None,
                           note=a.note or "", is_fixture=a.fixture)
    print("run", rid, file=sys.stderr)
    s = R.execute_run(root, rid, max_attempts=a.max_attempts, embed_image=a.embed_image,
                      timeouts=json.loads(a.timeouts) if a.timeouts else None,
                      log=lambda m: print(m, file=sys.stderr, flush=True))
    s.pop("attempt_log", None)
    print(json.dumps(s, indent=1, default=str))


def cmd_status(a):
    from . import runs as R
    print(json.dumps(R.summary(Path(a.root), a.run_id), indent=1, default=str))


def cmd_renormalise(a):
    from . import runs as R
    print(R.renormalise(Path(a.root), a.run_id))


def cmd_evaluate(a):
    from .report import evaluate_page_runs
    print(json.dumps(evaluate_page_runs(Path(a.root), a.dataset, a.page, a.revision), indent=1, ensure_ascii=False,
                     default=str)[:4000])


def cmd_compare(a):
    from .report import build_bundle
    p = build_bundle(Path(a.root), a.dataset, a.page)
    print(p)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="labocr")
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    s = sub.add_parser("ingest")
    s.add_argument("file")
    s.add_argument("--dataset", required=True)
    s.add_argument("--document-id", required=True)
    s.add_argument("--pages")
    s.add_argument("--category", required=True)
    s.add_argument("--languages", default="ar")
    s.add_argument("--provenance", default="")
    s.add_argument("--usage", default="private")
    s.add_argument("--split", default="none")
    s.set_defaults(fn=cmd_ingest)
    s = sub.add_parser("render")
    s.add_argument("--dataset", required=True)
    s.add_argument("--dpi", type=int, default=300)
    s.add_argument("--rgb", action="store_true")
    s.set_defaults(fn=cmd_render)
    s = sub.add_parser("run")
    s.add_argument("--dataset")
    s.add_argument("--engine")
    s.add_argument("--variant", default="default")
    s.add_argument("--worker-json")
    s.add_argument("--settings")
    s.add_argument("--revision")
    s.add_argument("--pages")
    s.add_argument("--note")
    s.add_argument("--resume")
    s.add_argument("--fixture", action="store_true")
    s.add_argument("--embed-image", action="store_true")
    s.add_argument("--max-attempts", type=int, default=2)
    s.add_argument("--timeouts")
    s.set_defaults(fn=cmd_run)
    s = sub.add_parser("status")
    s.add_argument("run_id")
    s.set_defaults(fn=cmd_status)
    s = sub.add_parser("renormalise")
    s.add_argument("run_id")
    s.set_defaults(fn=cmd_renormalise)
    s = sub.add_parser("evaluate")
    s.add_argument("--dataset", required=True)
    s.add_argument("--page", required=True)
    s.add_argument("--revision")
    s.set_defaults(fn=cmd_evaluate)
    s = sub.add_parser("compare")
    s.add_argument("--dataset", required=True)
    s.add_argument("--page", required=True)
    s.set_defaults(fn=cmd_compare)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
