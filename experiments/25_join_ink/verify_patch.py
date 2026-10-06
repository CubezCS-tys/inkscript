"""The diff (penpath.patch, applied to a copy of src's penpath.py) cuts exactly as patch25's 'lumpfoot' variant:
the patched source is executed into the imported module in this process, the documents replayed, cuts compared.
    verify_patch.py PATCHED_PENPATH_PY DOC..."""
import sys, pickle
from replay import replay, DOCS, P
src = open(sys.argv[1]).read(); exec(compile(src, "penpath_patched", "exec"), P.__dict__)
from common import HERE
for doc in sys.argv[2:]:
    kept, _ = replay(doc, set(DOCS[doc]["pages"])); ref = {(p["page"], tuple(p["off"])): p["cuts"] for p in pickle.load(open(HERE / f"out/plans/lumpfoot_{doc}.pkl", "rb"))}
    same = sum(list(ref.get((r["page"], tuple(p["off"])), [])) == list(p["cuts"]) for r, p in kept)
    print(doc, f"same cuts as lumpfoot: {same}/{len(kept)}", flush=True)
