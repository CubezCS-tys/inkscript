"""The gold set (experiment 34): hand-checked pages every reader is scored on.

    gold/format.py   the page file (inkscript-gold/1): lines with boxes and exact text, reading order, regions,
                     tables, equations, articles; load / save (atomic) / progress; export to ALTO 4.4
    gold/text.py     the two normalisations (faithful, folded) and a fast edit distance
    gold/score.py    `inkscript score`: CER/WER, invented/dropped/repeated lines, TEDS, equation distance,
                     reading order; per kind and decade; bootstrap intervals over documents
"""
