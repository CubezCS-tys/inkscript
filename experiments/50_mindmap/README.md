# Experiment 50: the Mandumah product map

**Question** (owner, 2026-10-21). An in-depth, interactive mind map of what Mandumah offers. It should cover:
- the nitty-gritty of the RAG (ai.mandumah.com);
- the Web-of-Science platform's tables;
- the pipeline, the Desk and the plans.

Nodes can be dragged, zoomed, opened and searched.

**Answer.** 553 nodes and 75 cross-links, in three areas:

| Area | Nodes | Source |
|---|---|---|
| Mandumah's product line | 27 | the AI-Search session's own notes (search.mandumah.com, the six databases, the journal lists, the AI platform, cost tiers, ops, seven weak spots) |
| AI-Search (ai.mandumah.com) | 261 | an agent reading the AI-Search and AI-Search-Mandumah repos, read-only (products, the 13-step pipeline, the 3 Qdrant collections, ids, MySQL, Redis, S3, ingest, ops, problems, roadmap, 31 ADRs) |
| inkscript | 265 | an agent reading this repo (the vision, sources, pipeline, outputs, all 83 platform v2 tables with their key columns, linking, the Desk, planned products and metrics, ops); the RAG chunk node was filled in from the 2026-10-21 work with AI-Search |

Every node carries its `source`. Unknowns are stated, not guessed. Examples: which AI-Search switches are on in
production, current point counts (the docs' figures are from 2026-09-28), and search.mandumah.com's tiers and
prices. Platform v2 row counts are from its README, before all 600 articles were loaded.

**How to see it.** It is served at `127.0.0.1:8004/mindmap/` (from `experiments/49_correction_desk/out/site/`).
Open it through the tunnel `ssh -N -L 9004:127.0.0.1:8004 prod` at http://localhost:9004/mindmap/.

**Files.**
- `NODE_FORMAT.md`: the node format the agents wrote to.
- `viewer.html`: D3 force layout. Drag to pin, double-click to unpin, scroll to zoom, click to open and show
  details, search with Arabic folding, toggle cross-links; light and dark.
- `build.py`: merges `out/ai_search.json`, `out/inkscript.json` and `out/mandumah_products.json` into
  `out/mindmap.html` and `out/mindmap.json`, checking ids and links.
