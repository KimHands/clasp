# AGENTS.md

Guidance for coding agents working in this repository.

---

## Project Overview

**Clasp** is a privacy-first desktop app for automatic local file classification and mind-map visualization. It uses a 3-tier engine (rules → embeddings → LLM) to classify files and display results as an interactive graph.

**Stack**: Electron 40 + React 19 + Vite 7 (frontend) + Python FastAPI (backend on a per-launch loopback port). Backend verified on Python 3.12.

**Transfer boundary**: file content and file names may only go to a loopback LLM server (`engines/tier3_llm.py`). Tests in `backend/tests/test_transfer_boundary.py` pin this. The first scan still downloads the embedding model from Hugging Face.

---

## Development Commands

### Run (backend auto-starts)

```bash
cd frontend
npm install          # first time only
npm run dev:electron # Vite dev server (5173) + Electron + backend
```

Electron's `main.cjs` picks a free port and a per-launch token, spawns the backend (`backend/venv/bin/python -m uvicorn`), waits for an authenticated `GET /health`, then opens the window. The backend rejects requests without `X-Clasp-Token`. Set `CLASP_VITE_PORT` if 5173 is taken.

### First-time backend setup

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The first scan downloads the sentence-transformers model automatically.

### Lingering dev processes

Check what owns a port before stopping it, because other projects may use the same ports:

```bash
lsof -nP -iTCP:5173 -sTCP:LISTEN
```

Stop only the PIDs that belong to this repository.

### Tests

```bash
cd backend
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest
```

Classification evaluation (see `docs/evaluation.md`):

```bash
venv/bin/python -m eval.run --split tune
```

Change `CLASSIFIER_VERSION` in `engines/pipeline.py` when classification logic changes, so unchanged files are reclassified.

### Production Build

```bash
./build.sh
# Output: frontend/release/ (macOS DMG / Windows NSIS)
```

The macOS build targets the host architecture (arm64) and is not signed. The Windows branch is not verified by a real build yet.

---

## Architecture

```
Electron Shell (main.cjs)
  └─ React + Vite Renderer (localhost:5173 in dev, dist/ in prod)
       └─ Pages and Zustand stores → src/api/ (fetch + token) → HTTP 127.0.0.1:<port>
                                                    │
                                          Python FastAPI Backend
                                          ┌────────────────────┐
                                          │ routers/           │
                                          │ services/          │
                                          │ engines/ (3-tier)  │
                                          │ SQLite (clasp.db)  │
                                          └────────────────────┘
```

### 3-Tier Classification Pipeline (`backend/engines/pipeline.py`)

```
Tier 1 — Rule-based (always runs)
  Sources in order: manual classification (1.0) → user rules (0.85)
                    → specific format extensions, built-in and custom (0.85)
                    → filename patterns on general formats (0.82)
                    → general formats such as pdf, docx, txt (0.50)
  A manual classification returns immediately

Tier 2 — sentence-transformers embedding + cosine similarity
  model: paraphrase-multilingual-MiniLM-L12-v2
  Runs when extracted or cover text is available
  T1 + T2 agree on category → max(T1, T2) + 0.05, capped at 0.95
  Otherwise T2 wins only when its score is higher than T1

Tier 3 — local LLM over an OpenAI-compatible API, off by default
  Runs when enabled and the best score so far is < 0.85
  Output is validated against the category allow-list and capped at 0.85
  Replaces the candidate only when its score is higher

Unclassified: confidence_score < 0.31 → isolated, excluded from file moves
```

Cover page detection: PDF/DOCX first-page text (< 300 chars + date/student-ID pattern) is extracted separately and stored in `cover_pages`. Files with cover embedding cosine similarity ≥ 0.80 are auto-grouped under the same tag.

### Frontend State Management

Six Zustand stores in `frontend/src/store/`:
- `scanStore` — folder selection, scan ID, SSE progress (7 stages), recent folders
- `fileStore` — paginated classification results
- `ruleStore` — drag-and-drop rules
- `applyStore` — apply/undo state
- `extensionStore` — custom extension mappings
- `themeStore` — dark/light theme

All FastAPI calls are centralized in `frontend/src/api/`.

### Electron IPC (`frontend/electron/main.cjs`)

IPC handlers exposed via `contextBridge` (preload.cjs):
- `dialog:openFolder` — system folder picker
- `backend:getConfig` — backend URL and per-launch token for `src/api/`

---

## Critical Quirk: Electron + ESM

`package.json` uses `"type": "module"` for Vite/React. Electron's main and preload files **must** use the `.cjs` extension so `require('electron')` resolves to Electron's internal API rather than the npm stub binary path string.

```
electron/main.cjs    ← CJS, must stay .cjs
electron/preload.cjs ← CJS, must stay .cjs
src/**/*.js(x)       ← ESM, handled by Vite
```

Never use `createRequire` to call `require('electron')`. It bypasses Electron's module patch.

---

## Database

- **Location (macOS)**: `~/Library/Application Support/Clasp/clasp.db`
- **ORM**: SQLAlchemy 2.0, WAL mode enabled
- Key tables: `files`, `classifications` (with `tier_used`, `confidence_score`, `is_manual`), `cover_pages` (embedding stored as JSON text), `cover_similarity_groups`, `action_logs` (Undo support), `action_batches` (Undo batch grouping), `action_log_identities` (moved file identity), `app_settings`, `sensitive_keywords`, `rules`, `custom_extensions`, `custom_categories`

Manual classification (`is_manual=true`, `confidence_score=1.0`) also triggers `tier2_embedding.apply_feedback()` for online embedding correction (learning_rate=0.15).

---

## Read-only MCP Server

`backend/mcp_server/` exposes classification results over stdio (see `docs/mcp.md`). Do not add tools that move files, and do not return file names or content by default, because the client may be a cloud LLM.

## Coding Rules

1. FastAPI route handlers must be `async`.
2. Use SQLAlchemy ORM — no raw SQL strings.
3. All classification results must include `tier_used` and `confidence_score`.
4. All frontend API calls go in `src/api/`. Components never call `fetch` directly.
5. Files with `confidence_score < 0.31` must be isolated and excluded from file moves.
6. Business logic comments: Korean. Technical implementation comments: English.
7. Cover page embeddings are JSON-serialized and stored in the `cover_pages.embedding` text column.

## Public Repository

This repository is public. Do not commit absolute local paths, personal file names, API keys, or local agent settings.
