# Node format for the Mandumah product mind map (experiment 50)

Write one JSON file: a single root object. Every node:

```json
{
  "id": "rag.retrieval.qdrant",          // unique, dot-separated path, lowercase a-z0-9_.
  "label": "Qdrant search",              // 1-5 words, shown on the map
  "kind": "product|component|service|store|table|table-group|process|metric|screen|person-role|doc|idea",
  "status": "live|built|prototype|designed|planned|idea",
  "summary": "One plain sentence: what it is and why it matters.",
  "details": ["short bullet facts with real numbers, names, ports, file paths", "..."],
  "source": "repo-relative path(s) where this is documented",
  "children": [ ... ]
}
```

Cross-links (things that feed each other, e.g. "platform v2 masters → RAG chunks") go in a top-level array
`"links": [{"from": "<id>", "to": "<id>", "label": "feeds chunks"}]` on the root only.

Rules:
- **Depth:** go to the nitty-gritty. Depth 4–6 is fine where it is real, for example product → subsystem →
  component → table → key columns. Aim for 150–400 nodes for your side.
- **Facts only from the docs and code you read.** Put the file in `source`. Where something is unclear, say so
  in `details` rather than guessing.
- **No secrets:** no passwords, keys, tokens, `.env` values, internal IPs or customer personal data. Institution
  names that appear in the docs are fine.
- **Plain English.** Arabic is fine for proper names.
