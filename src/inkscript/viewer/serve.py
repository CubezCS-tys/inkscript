"""`inkscript view OUT_DIR`: the outputs of a build in the browser — the scan with every ALTO word on it, the
JATS as an article, the two linked, and both XML files as written.

    inkscript view OUT_DIR [--doc ID] [--port 8765] [--host 127.0.0.1] [--scan-dir DIR] [--dpi 150]
    inkscript view OUT_DIR --static DIR [--doc ID ...]      a folder that opens from disk (file://), no server

One URL scheme for both (the app does not know which it is talking to, except that a static bundle's data
comes as small .js files, because Chrome does not let a page fetch() files from disk):

    index.html, app.js, app.css             the app (src/inkscript/viewer/app/, no external library)
    data/index.json                         the picker's rows
    data/<id>/doc.json                      page sizes, ALTO tags (marks, reasons, quotations), processing steps
    data/<id>/page-<n>.json                 one page: blocks > lines > words (box, text, confidence, mark...)
    data/<id>/page-<n>.png                  the page image (pymupdf, cached on disk under ~/.cache/inkscript/view)
    data/<id>/article.json                  {html, linked, words}: the JATS rendered, words linked to ALTO ids
    data/<id>/alto.xml, jats.xml            the files as written

Nothing is sent anywhere: the server binds to 127.0.0.1 unless --host says otherwise (e.g. 0.0.0.0 to read on
a phone on the same network).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .outputs import Outputs

APP = Path(__file__).with_name("app")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
         ".png": "image/png", ".xml": "application/xml; charset=utf-8", ".svg": "image/svg+xml"}
_PAGE = re.compile(r"^page-(\d+)\.(json|png)$")


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "inkscript" / "view"


class Data:
    """The data paths of the URL scheme above -> (bytes, content type); shared by the server and --static."""

    def __init__(self, outputs: Outputs, dpi: int = 150, cache: Path | None = None):
        self.o, self.dpi = outputs, dpi
        self.cache = cache

    def get(self, path: str) -> tuple[bytes, str]:
        parts = path.split("/")
        if parts == ["index.json"]:
            rows = sorted(self.o.index(), key=lambda r: r["id"])
            return _json(dict(docs=rows, out_dir=str(self.o.out_dir))), TYPES[".json"]
        if len(parts) != 2:
            raise KeyError(path)
        stem, name = parts
        d = self.o.doc(stem)
        if name == "doc.json":
            return _json(d.summary()), TYPES[".json"]
        if name == "article.json":
            return _json(d.article()), TYPES[".json"]
        if name == "alto.xml":
            return d.alto_path.read_bytes(), TYPES[".xml"]
        if name == "jats.xml":
            return d.jats_path.read_bytes(), TYPES[".xml"]
        m = _PAGE.match(name)
        if m:
            n = int(m[1])
            if n not in d.page_numbers():
                raise KeyError(path)
            if m[2] == "json":
                return _json(d.page(n)), TYPES[".json"]
            return self.image(d, n), TYPES[".png"]
        raise KeyError(path)

    def image(self, d, n: int) -> bytes:
        if d.pdf is None:
            raise KeyError(f"{d.stem}: no PDF to draw page {n} from")
        st = d.pdf.stat()
        key = hashlib.sha1(f"{d.pdf.resolve()}|{st.st_size}|{st.st_mtime_ns}|{self.dpi}".encode()).hexdigest()[:16]
        f = self.cache / d.stem / f"{key}-{n}.png" if self.cache else None
        if f and f.exists():
            return f.read_bytes()
        png = d.image(n, self.dpi)
        if f:
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_suffix(".tmp")
            tmp.write_bytes(png)
            tmp.replace(f)
        return png


def _json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _app_file(name: str) -> bytes:
    return (APP / name).read_bytes()


def make_handler(data: Data):
    class H(BaseHTTPRequestHandler):
        server_version = "inkscript-view"

        def log_message(self, fmt, *args):          # quiet: one line per error only
            if args and str(args[1]).startswith(("4", "5")):
                sys.stderr.write("view: " + fmt % args + "\n")

        def send(self, body: bytes, ctype: str, status=HTTPStatus.OK, cache=False):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "max-age=3600" if cache else "no-cache")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path).lstrip("/")
            try:
                if path in ("", "index.html"):
                    return self.send(_app_file("index.html"), TYPES[".html"])
                if path in ("app.js", "app.css"):
                    return self.send(_app_file(path), TYPES[Path(path).suffix])
                if path.startswith("data/"):
                    body, ctype = data.get(path[5:])
                    return self.send(body, ctype, cache=ctype == TYPES[".png"])
            except KeyError as e:
                return self.send(f"not found: {e}".encode(), "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as e:                   # one bad file must not stop the viewer
                return self.send(f"{type(e).__name__}: {e}".encode(), "text/plain; charset=utf-8",
                                 HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send(b"not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
    return H


def serve(outputs: Outputs, host="127.0.0.1", port=8765, doc=None, dpi=150, open_browser=False) -> int:
    data = Data(outputs, dpi, cache_dir())
    n = len(outputs.docs())
    if not n:
        print(f"no <id>.alto.xml with its <id>.jats.xml under {outputs.out_dir} (build with `inkscript native --xml`)")
        return 1
    if doc and doc not in outputs.docs():
        print(f"{doc}: not found under {outputs.out_dir}")
        return 1
    httpd = ThreadingHTTPServer((host, port), make_handler(data))
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{httpd.server_address[1]}/"
    if doc:
        url += f"#/doc/{urllib.parse.quote(doc)}"
    print(f"{n} document(s) from {outputs.out_dir}\nopen {url}   (Ctrl+C to stop)", flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def export(outputs: Outputs, dest: Path, docs=None, dpi=150) -> dict:
    """A static bundle: the app and every data path as a .js file that hands its content to the app
    (window.__put(path, value)), page images as PNG files; opens from disk with no server."""
    dest = Path(dest)
    data = Data(outputs, dpi, cache_dir())
    stems = list(docs) if docs else list(outputs.docs())
    for s in stems:
        if s not in outputs.docs():
            raise KeyError(f"{s}: not found under {outputs.out_dir}")
    (dest / "data").mkdir(parents=True, exist_ok=True)
    html = _app_file("index.html").decode("utf-8").replace("<!--STATIC-->", "<script>window.STATIC=true</script>")
    (dest / "index.html").write_text(html, encoding="utf-8")
    for f in ("app.js", "app.css"):
        shutil.copyfile(APP / f, dest / f)

    def put(path, body: bytes, ctype: str):
        out = dest / "data" / path
        out.parent.mkdir(parents=True, exist_ok=True)
        if ctype == TYPES[".png"]:
            out.write_bytes(body)
            return
        value = body.decode("utf-8") if ctype == TYPES[".xml"] else None
        js = ("window.__put(" + json.dumps(path, ensure_ascii=False) + "," +
              (json.dumps(value, ensure_ascii=False) if value is not None else body.decode("utf-8")) + ");\n")
        out.with_name(out.name + ".js").write_text(js, encoding="utf-8")

    keep = set(stems)
    full = outputs.index()
    rows = [r for r in full if r["id"] in keep]
    put("index.json", _json(dict(docs=sorted(rows, key=lambda r: r["id"]), out_dir=str(outputs.out_dir))),
        TYPES[".json"])
    n_pages = 0
    for s in stems:
        d = outputs.doc(s)
        for name in ("doc.json", "article.json", "alto.xml", "jats.xml"):
            put(f"{s}/{name}", *data.get(f"{s}/{name}"))
        for n in d.page_numbers():
            put(f"{s}/page-{n}.json", *data.get(f"{s}/page-{n}.json"))
            if d.pdf is not None:
                put(f"{s}/page-{n}.png", *data.get(f"{s}/page-{n}.png"))
            n_pages += 1
    return dict(docs=len(stems), pages=n_pages, path=str(dest))


def main(a) -> int:
    outputs = Outputs(a.out_dir, a.scan_dir)
    if a.static:
        docs = a.doc or None
        r = export(outputs, Path(a.static), docs, a.dpi)
        print(f"wrote {r['docs']} document(s), {r['pages']} page(s) to {r['path']}; open {Path(r['path']).resolve() / 'index.html'}")
        return 0
    return serve(outputs, a.host, a.port, (a.doc or [None])[0], a.dpi, a.open)
