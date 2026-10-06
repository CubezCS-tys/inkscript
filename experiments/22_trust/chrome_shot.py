"""Screenshot the _trust.pdf in a real Chromium 153 (the playwright venv and browser experiment 23 set up in the
session scratchpad): one page at page width, then the same with the mouse resting on a flagged word (its note pops up).

    PW_PY chrome_shot.py PDF PAGE X_PT Y_PT OUT_PREFIX     (X_PT, Y_PT: a point inside a flagged word, PDF points from top-left)
"""
import sys, asyncio
from playwright.async_api import async_playwright
SP = "/tmp/claude-1000/-home-yassine-inkscript/ed816869-9be5-4008-b630-480b426fc462/scratchpad"
EXE = SP + "/browsers/chromium-1243/chrome-linux64/chrome"


async def main(pdf, page, x, y, out):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=EXE, headless=True, args=["--headless=new"])
        ctx = await b.new_context(viewport={"width": 760, "height": 1000})
        pg = await ctx.new_page()
        await pg.goto(f"file://{pdf}#page={page}&zoom=150,0,0&toolbar=0&navpanes=0"); await pg.wait_for_timeout(4000)
        await pg.mouse.move(5, 5); await pg.wait_for_timeout(300)
        await pg.screenshot(path=out + "_page.png")
        s = 150 / 100 * 96 / 72
        await pg.mouse.move(x * s, y * s); await pg.wait_for_timeout(1200)
        await pg.screenshot(path=out + "_hover.png")
        await b.close()

asyncio.run(main(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]))
