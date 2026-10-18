"""Exercise the local viewer, playback pixels and recording without saving test data."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
CHECKS = HERE / "out" / "checks"


def run(url):
    CHECKS.mkdir(parents=True, exist_ok=True)
    errors, checks = [], {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=dict(width=1440, height=1000), device_scale_factor=1)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle")
        page.wait_for_function("document.getElementById('raster').naturalWidth > 0")
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(CHECKS / "desktop.png"), full_page=True)
        checks["desktop_no_overflow"] = page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        checks["arabic_font_loaded"] = page.evaluate("document.fonts.check('24px Scheherazade')")
        page.locator('#reader-mode').select_option('sequence')
        checks["reader_selector"] = page.locator('.reading > span').first.inner_text() == 'CTC reading'
        page.locator('#reader-mode').select_option('retrieval')
        page.locator("#ghost").uncheck()
        page.locator("#restart").click()
        before = page.locator("#reference-canvas").evaluate("c => c.toDataURL()")
        page.locator("#play").click()
        page.wait_for_timeout(700)
        middle = page.locator("#reference-canvas").evaluate("c => c.toDataURL()")
        page.wait_for_timeout(500)
        later = page.locator("#reference-canvas").evaluate("c => c.toDataURL()")
        page.locator("#play").click()
        checks["playback_moves"] = before != middle and middle != later
        checks["canvas_nonblank"] = page.locator("#reference-canvas").evaluate(
            "c => { const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0; "
            "for(let i=3;i<d.length;i+=4) if(d[i]) n++; return n>100; }")
        selected = page.locator("#sample-id").text_content()
        page.locator("#next").click()
        page.wait_for_function("s => document.getElementById('sample-id').textContent !== s", arg=selected)
        checks["next_sample"] = selected != page.locator("#sample-id").text_content()
        page.locator("#search").fill("no-matching-sample-zzzz")
        page.wait_for_function("document.getElementById('sample-id').textContent === 'No sample selected'")
        checks["empty_state"] = page.locator("#download").is_disabled()
        page.locator("#search").fill("")
        page.wait_for_function("document.getElementById('transcription').textContent.length > 0")
        page.locator('[data-view="results"]').click()
        page.screenshot(path=str(CHECKS / "results.png"), full_page=True)
        checks["results_rows"] = page.locator("#retrieval-table tbody tr").count() == 3
        page.locator('[data-view="capture"]').click()
        box = page.locator("#capture-canvas").bounding_box()
        page.mouse.move(box["x"] + 90, box["y"] + 90)
        page.mouse.down()
        page.mouse.move(box["x"] + 180, box["y"] + 60, steps=12)
        page.mouse.move(box["x"] + 230, box["y"] + 140, steps=12)
        page.mouse.up()
        checks["recorded_stroke"] = page.locator("#capture-count").inner_text().startswith("1 stroke")
        checks["mouse_not_mislabelled_pen"] = page.locator("#device").inner_text() == "mouse input"
        captured_payloads = []

        def reject(route):
            captured_payloads.append(route.request.post_data_json)
            route.fulfill(status=400, content_type="application/json", body='{"error":"Test rejection; nothing saved"}')

        page.route("**/api/captures", reject)
        page.locator("#save").click()
        page.wait_for_function("document.getElementById('capture-status').textContent.includes('Test rejection')")
        checks["failed_save_retains_ink"] = page.locator("#capture-count").inner_text().startswith("1 stroke")
        points = captured_payloads[0]["strokes"][0]
        checks["capture_channels_and_time"] = len(points) >= 20 and all(len(x) == 6 for x in points) and all(
            a[2] <= b[2] for a, b in zip(points, points[1:]))
        page.screenshot(path=str(CHECKS / "recording.png"), full_page=True)
        page.locator("#undo").click()
        checks["undo"] = page.locator("#capture-count").inner_text().startswith("0 strokes")
        page.set_viewport_size(dict(width=390, height=844))
        page.locator('[data-view="samples"]').click()
        page.wait_for_timeout(200)
        page.screenshot(path=str(CHECKS / "mobile.png"), full_page=True)
        checks["mobile_no_overflow"] = page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator('[data-view="capture"]').click()
        page.screenshot(path=str(CHECKS / "mobile-recording.png"), full_page=True)
        checks["mobile_capture_no_overflow"] = page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        checks["no_browser_errors"] = not errors
        browser.close()
    result = dict(checks=checks, errors=errors)
    (CHECKS / "browser.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    assert all(checks.values()), result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8842")
    run(parser.parse_args().url)
