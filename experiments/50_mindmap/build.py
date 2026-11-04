"""Merge the mind-map halves into one tree and write the page (experiment 50).

    python3 build.py [--sample]

Reads out/ai_search.json, out/inkscript.json and, if present, out/mandumah_products.json (Mandumah's product line
from the AI-Search session). Writes out/mindmap.html (viewer.html with the data inlined) and out/mindmap.json.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def load(name):
    p = OUT / name
    return json.loads(p.read_text()) if p.exists() else None


def sample():
    return {"id": "ai_search", "label": "AI-Search (ai.mandumah.com)", "kind": "product", "status": "live",
            "summary": "Sample node.", "children": [
                {"id": "ai_search.ingest", "label": "Ingest", "kind": "process", "status": "live", "summary": "Sample.",
                 "children": [{"id": "ai_search.ingest.chunker", "label": "Chunker", "kind": "component", "status": "live"}]}]}


def main():
    halves = [load("mandumah_products.json"), load("ai_search.json") or (sample() if "--sample" in sys.argv else None),
              load("inkscript.json")]
    halves = [h for h in halves if h]
    links = []
    for h in halves:
        links += h.pop("links", []) or []
    root = {"id": "mandumah", "label": "Mandumah (دار المنظومة)", "kind": "product", "status": "live",
            "summary": "Mandumah's products and the platform being built around its archive.",
            "details": ["Built from: the AI-Search repo (read-only), the inkscript repo, and notes from the AI-Search session (2026-10-21)."],
            "children": halves, "links": links}
    ids, dup = set(), []

    def walk(n):
        if n["id"] in ids:
            dup.append(n["id"])
        ids.add(n["id"])
        for c in n.get("children") or []:
            walk(c)
    walk(root)
    bad = [l for l in links if l["from"] not in ids or l["to"] not in ids]
    root["links"] = [l for l in links if l["from"] in ids and l["to"] in ids]
    print(f"{len(ids)} nodes, {len(root['links'])} links kept, {len(bad)} dropped (missing ends), {len(dup)} duplicate ids")
    for l in bad[:10]:
        print("  dropped link", l)
    for d in dup[:10]:
        print("  duplicate id", d)
    data = json.dumps(root, ensure_ascii=False).replace("</", "<\\/")
    html = (HERE / "viewer.html").read_text().replace("__MAPDATA__", data)
    (OUT / "mindmap.html").write_text(html)
    (OUT / "mindmap.json").write_text(json.dumps(root, ensure_ascii=False, indent=1))
    print("wrote", OUT / "mindmap.html", f"({len(html.encode()) // 1024} KB)")


if __name__ == "__main__":
    main()
