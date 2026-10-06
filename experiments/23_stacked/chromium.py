"""Drive a real Chromium 153 (Chrome for Testing 153.0.8010.12, the version D18 used; playwright in a scratch venv)
over a PDF: for one word, drag from the right of its first letter to the middle of each letter in turn; after each
drag take a screenshot, find the highlight (pixels the selection tinted), and copy (Ctrl+C, pasted into a textarea).

    PW_PY chromium.py PDF PAGE WORD [OUTNAME] [--line]      -> out/chromium/OUTNAME_*.png, OUTNAME.json

The page is opened at 400% with the word in view; screen <-> PDF points is found by matching the screenshot to a
pdfium-independent render (PyMuPDF) of the same page. Needs PyMuPDF and opencv in the playwright venv's reach: the
geometry is computed by the repo's venv beforehand (glyphs.py) and passed in as JSON.
"""
import sys, json, asyncio, subprocess
from pathlib import Path
import numpy as np, cv2
from playwright.async_api import async_playwright
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
SP = Path("/tmp/claude-1000/-home-yassine-inkscript/ed816869-9be5-4008-b630-480b426fc462/scratchpad")
EXE = str(SP / "browsers/chromium-1243/chrome-linux64/chrome")
S = 400 / 100 * 96 / 72                                     # css px per point at 400%


def geometry(pdf, page, word):
    code = f"""
import sys, json, fitz; sys.path.insert(0, {str(HERE)!r}); import glyphs as G
doc = fitz.open({pdf!r}); gl = G.glyphs(doc, {page}); runs = G.find_word(gl, {word!r})
H = doc[{page} - 1].rect.height
print(json.dumps(dict(H=H, runs=[[dict(text=g['text'], box=g['box'], origin=g['origin']) for g in r] for r in runs])))
"""
    r = subprocess.run([str(REPO / ".venv/bin/python"), "-c", code], capture_output=True, text=True)
    return json.loads(r.stdout.strip().splitlines()[-1])


def render(pdf, page, s):
    out = SP / "render.png"
    subprocess.run([str(REPO / ".venv/bin/python"), "-c", f"import fitz; p=fitz.open({pdf!r})[{page}-1]; p.get_pixmap(matrix=fitz.Matrix({s},{s}), colorspace=fitz.csGRAY).save({str(out)!r})"], check=True)
    return cv2.imread(str(out), 0)


async def main(pdf, page, word, name, line=False):
    page = int(page); geo = geometry(pdf, page, word); H = geo["H"]
    run = geo["runs"][0]; gx0 = min(g["box"][0] for g in run); gx1 = max(g["box"][2] for g in run)
    top = max(g["box"][3] for g in run)
    od = HERE / "out/chromium"; od.mkdir(parents=True, exist_ok=True)
    R = render(pdf, page, S); res = dict(pdf=pdf, page=page, word=word, glyphs=run, drags=[])
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=EXE, headless=True, args=["--headless=new"])
        ctx = await b.new_context(viewport={"width": 900, "height": 500})
        pg = await ctx.new_page()
        await pg.goto(f"file://{pdf}#page={page}&zoom=400,{gx0 - 40:.0f},{H - top - 15:.0f}&toolbar=0&navpanes=0"); await pg.wait_for_timeout(4000)
        for it in range(4):
            await pg.mouse.move(450, 250); await pg.wait_for_timeout(300)
            base = await pg.screenshot(); B = cv2.imdecode(np.frombuffer(base, np.uint8), 1)
            g = cv2.cvtColor(B, cv2.COLOR_BGR2GRAY); T = g[100:400, 100:750]
            r = cv2.matchTemplate(R, T, cv2.TM_CCOEFF_NORMED); _, mv, _, ml = cv2.minMaxLoc(r)
            ox, oy = ml[0] - 100, ml[1] - 100                  # render px of screen (0,0)
            wx, wy = (gx0 + gx1) / 2 * S - ox, (H - top) * S - oy
            if 150 < wx < 750 and 150 < wy < 350: break
            await pg.mouse.wheel(wx - 450, wy - 250); await pg.wait_for_timeout(700)
        S_ = S
        to_scr = lambda x, y: (x * S_ - ox, (H - y) * S_ - oy)
        res["match"] = mv
        res["to_screen"] = [float(S_), ox, oy, H]
        cv2.imwrite(str(od / f"{name}_base.png"), B)
        y_mid = (min(g["box"][1] for g in run) + top) / 2
        sx = to_scr(max(g["box"][2] for g in run) + 1.5, y_mid)
        targets = list(range(len(run)))[::-1]                  # stream order is left->right; reading starts at the right
        ends = [((gl["box"][0] + gl["box"][2]) / 2, (gl["box"][1] + gl["box"][3]) / 2) for gl in run]
        if line: ends = [(gx0 - 200, y_mid)]; targets = [0]
        cb = await ctx.new_page(); await cb.set_content("<textarea id=t></textarea>"); await pg.bring_to_front()
        single = "--single" in sys.argv
        for n, i in enumerate(targets):
            ex, ey = to_scr(*ends[i])
            if single:                                         # select this letter alone: from just inside its right edge to just inside its left
                bx = run[i]["box"]; sx = to_scr(bx[2] - 0.15, y_mid); ex, ey = to_scr(bx[0] + 0.15, y_mid)
            await pg.mouse.move(5, 5); await pg.mouse.click(5, 5); await pg.wait_for_timeout(200)
            await pg.mouse.move(*sx); await pg.mouse.down(); await pg.mouse.move(ex, ey, steps=12); await pg.mouse.up(); await pg.wait_for_timeout(400)
            shot = cv2.imdecode(np.frombuffer(await pg.screenshot(), np.uint8), 1)
            await pg.keyboard.press("Control+c"); await pg.wait_for_timeout(200)
            await cb.bring_to_front(); await cb.fill("#t", ""); await cb.focus("#t"); await cb.keyboard.press("Control+v"); await cb.wait_for_timeout(150)
            txt = await cb.input_value("#t"); await pg.bring_to_front()
            d = (shot.astype(int) - B.astype(int)); m = np.abs(d).max(2) > 20
            ys, xs = np.where(m); hl = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
            hl_pt = [(hl[0] + ox) / S_, H - (hl[3] + oy) / S_, (hl[2] + ox) / S_, H - (hl[1] + oy) / S_] if hl else None
            cv2.imwrite(str(od / f"{name}_{n}.png"), shot)
            res["drags"].append(dict(to=i, text=txt, highlight_px=hl, highlight_pt=hl_pt, start=sx, end=[ex, ey]))
            print(n, repr(txt), hl_pt and [round(v, 1) for v in hl_pt], flush=True)
        await b.close()
    json.dump(res, open(od / f"{name}.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    asyncio.run(main(a[0], a[1], a[2], a[3] if len(a) > 3 else "test", "--line" in sys.argv))
