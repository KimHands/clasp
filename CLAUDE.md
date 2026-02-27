# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**Clasp** is a privacy-first desktop app for automatic local file classification and mind-map visualization. It uses a 3-tier AI engine (rules → embeddings → LLM) to classify files and display results as an interactive graph. All processing is local by default — file contents are never sent to external servers unless the user explicitly provides an API key for Tier 3.

**Stack**: Electron 40 + React 19 + Vite 7 (frontend) + Python FastAPI (backend at `localhost:8000`)

---

## Development Commands

### Backend

```bash
cd backend
source venv/bin/activate
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

First run downloads the sentence-transformers model (~500MB) automatically.

### Frontend (Electron + React)

```bash
cd frontend
npm install
npm run dev:electron   # Vite dev server (5173) + Electron app
```

### Kill lingering dev processes

```bash
lsof -ti:5173 -ti:8000 | xargs kill -9
```

### Production Build

```bash
chmod +x build.sh
./build.sh
# Output: frontend/release/ (macOS DMG / Windows NSIS)
```

Build sequence: PyInstaller bundles backend → Vite builds frontend → electron-builder packages app.

---

## Architecture

```
Electron Shell (main.cjs)
  └─ React + Vite Renderer (localhost:5173 in dev, dist/ in prod)
       └─ Zustand Stores → src/api/ (axios) → HTTP localhost:8000
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
  confidence ≥ 0.80 → return result
  otherwise → Tier 2

Tier 2 — sentence-transformers embedding + cosine similarity
  model: paraphrase-multilingual-MiniLM-L12-v2
  confidence ≥ 0.50 → return result
  T1 + T2 agree on category → ensemble boost (+0.10, capped at 1.0)
  confidence < 0.50 + API key present → Tier 3

Tier 3 — OpenAI API (optional, user must supply key)
  Use only when T3 beats max(T1, T2) score

Unclassified: confidence_score < 0.31 → isolated, excluded from file moves
```

Cover page detection: PDF/DOCX first-page text (< 300 chars + date/student-ID pattern) is extracted separately and stored in `cover_pages`. Files with cover embedding cosine similarity ≥ 0.75 are auto-grouped under the same tag.

### Frontend State Management

Six Zustand stores in `frontend/src/store/`:
- `scanStore` — folder selection, scan ID, SSE progress (7 stages), recent folders
- `fileStore` — paginated classification results
- `ruleStore` — drag-and-drop rules
- `applyStore` — apply/undo state
- `extensionStore` — custom extension mappings
- `themeStore` — dark/light theme

All FastAPI calls are centralized in `frontend/src/api/` — never call axios directly from components.

### Electron IPC (`frontend/electron/main.cjs`)

IPC handlers exposed via `contextBridge` (preload.cjs):
- `dialog:openFolder` — system folder picker
- `app:setEnv` / `app:getEnv` — API key storage via `safeStorage` (encrypted on disk at `~/Library/Application Support/clasp-settings.json`)

On startup, `main.cjs` spawns the backend process, polls `GET /docs` to wait for readiness, then syncs stored API keys to backend via HTTP before creating the window.

---

## Critical Quirk: Electron + ESM

`package.json` uses `"type": "module"` for Vite/React. Electron's main and preload files **must** use `.cjs` extension to force CommonJS loading so `require('electron')` resolves to Electron's internal API (not the npm stub binary path string).

```
electron/main.cjs    ← CJS, must stay .cjs
electron/preload.cjs ← CJS, must stay .cjs
src/**/*.js(x)       ← ESM, handled by Vite
```

Never use `createRequire` to call `require('electron')` — it bypasses Electron's module patch.

---

## Database

- **Location (macOS)**: `~/Library/Application Support/Clasp/clasp.db`
- **ORM**: SQLAlchemy 2.0, WAL mode enabled
- Key tables: `files`, `classifications` (with `tier_used`, `confidence_score`, `is_manual`), `cover_pages` (embedding stored as JSON text), `cover_similarity_groups`, `action_logs` (Undo support), `rules`, `custom_extensions`

Manual classification (`is_manual=true`, `confidence_score=1.0`) takes priority in the next scan's Tier 1 lookup. It also triggers `tier2_embedding.apply_feedback()` for online embedding correction (learning_rate=0.05).

---

## Coding Rules

1. FastAPI route handlers and services must be `async`.
2. Use SQLAlchemy ORM — no raw SQL strings.
3. All classification results must include `tier_used` and `confidence_score`.
4. All frontend API calls go in `src/api/` — components use Zustand stores only.
5. Files with `confidence_score < 0.31` must be isolated and excluded from file moves.
6. Business logic comments: Korean. Technical implementation comments: English.
7. Cover page embeddings are JSON-serialized and stored in the `cover_pages.embedding` text column.
