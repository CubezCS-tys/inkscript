"""The live feeler page for the BEST method (hybrid_ctc_geo) on the held-out test pages: out/feel_best.html."""
import json
import bench, make_page as MP

d = json.load(open(bench.OUT / "report_data.json"))
final = [json.loads(l) for l in open(bench.LOG)]
r = [x for x in final if x["method"] == "hybrid_ctc_geo" and x["split"] == "test"][-1]
by = {}
for v in r["docs"].values():
    for k, (a, n) in v["by_len"].items(): by.setdefault(k, [0, 0]); by[k][0] += a; by[k][1] += n
summary = dict(train=["the train pages of each book"], pieces=r["total"]["pieces"], right=r["total"]["right"],
               letters_right=r["total"]["mean_doc_letter_acc"], by_len=by)
page = MP.PAGE
for a, b in [("From what it remembers feeling on pages __TRAIN__,", "A small reader trained on the feel of the train pages of all four books (never the picture),"),
             ("The feeler is crude on purpose: it matches remembered feelings, stretched evenly, with no model trained and no knowledge of words. Tooth letters (ب ت ث ن ي) feel alike and are told apart by their taps, which this face often prints as one blob.",
              "The best feeler (hybrid_ctc_geo): a trained reader names the letters from the feeling; the pen path decides where they split. Pages shown were never seen in training or tuning; the list mixes the reference book's whole test page with 80 pieces from each other book."),
             ("<title>Feeling the Word</title>", "<title>Feeling the Word, Best</title>")]:
    assert a in page, a[:40]; page = page.replace(a, b)
MP.PAGE = page
json.dump(dict(summary=summary, pieces=d["live"]), open(bench.OUT / "feel_best.json", "w"), ensure_ascii=False)
MP.main(bench.OUT / "feel_best.json", bench.OUT / "feel_best.html")
