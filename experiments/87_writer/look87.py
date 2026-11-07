"""Experiment 87: quick looks (specimens of the writer)."""
import sys, cv2, numpy as np, torch
torch.set_num_threads(2)
import writer87 as W

def specimen(lib, out, texts, **kw):
    rows = []
    for t in texts:
        g, inst, w = W.write_line(t, lib, dict(size=56.0), H=110, **kw)
        rows.append(g)
    Wm = max(r.shape[1] for r in rows)
    img = np.vstack([np.hstack([np.full((r.shape[0], Wm - r.shape[1]), 255, np.uint8), r]) for r in rows])
    cv2.imwrite(out, img)
    print(out, img.shape)

if __name__ == "__main__":
    lib = sys.argv[1]; out = sys.argv[2]
    specimen(lib, out, ["بسم الله الرحمن الرحيم", "كان من توفيق الله على أن أغرمت بالرحلات", "لديها ثلاثة أبناء وجميعهم في المدرسة",
                        "ظاهرة غريبة ضحك خفيف صوت شجرة"])
