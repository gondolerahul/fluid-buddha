# A2UI Backend Orchestrator

The "Brain" of the Voice-First Agentic UI Framework (A2UI) — a FastAPI service
that turns the **Pragya** widget on the HireBuddha site into a grounded, voice-first
SDR agent. It runs the dual-model cognitive loop, grounds every answer in the
**CORTEX** memory engine (`hb-cortex-memory`, Postgres + pgvector), and speaks +
draws dynamic UI over a single multiplexed WebSocket.

> **Mock mode is the default.** With `MOCK_AI=true` the entire stack — DB,
> ingestion, cognitive loop, voice transport — runs with **zero** Google Cloud
> setup using deterministic stub engines. Flip to `false` for real Vertex AI.

## Quickstart

### One command (Docker)

```bash
cd backend
docker compose up -d --build
```

This builds the orchestrator image and starts everything: Postgres + pgvector,
then the backend — which **auto-creates the schema and seeds CORTEX memory** from
the mounted website docs on first boot (idempotent via `--if-empty`). API on
`http://localhost:8080`, DB on host `:5434`.

```bash
curl localhost:8080/readyz
docker compose logs -f backend
docker compose down            # add -v to also wipe the DB volume
```

Default is mock mode. For Vertex: set `MOCK_AI=false` + `GOOGLE_CLOUD_PROJECT` in
`backend/.env`, uncomment the gcloud ADC volume/credentials lines in
`docker-compose.yml`, then `docker compose up -d --build`.

### Local (venv) — for iterating on the code

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                 # MOCK_AI=true by default

docker compose up -d postgres        # just the DB on :5434
.venv/bin/python -m ingestion.ingest --site hirebuddha   # seed CORTEX memory

.venv/bin/uvicorn app.main:app --reload --port 8080      # serve
# smoke tests:
.venv/bin/python -m scripts.smoke_chat
.venv/bin/python -m scripts.smoke_ws
.venv/bin/python -m pytest -q
```

## Going live on Vertex AI

1. `gcloud auth application-default login` (or set `GOOGLE_APPLICATION_CREDENTIALS`).
2. In `.env`: `MOCK_AI=false`, set `GOOGLE_CLOUD_PROJECT` / `VERTEX_LOCATION`.
3. Re-run ingestion so chunks are embedded with `text-embedding-004` (768-dim).

Models are configurable: `FAST_MODEL` (Fast Router), `HEAVY_MODEL` (Heavy Thinker),
`EMBED_MODEL`, `TTS_VOICE`, `ASR_LANGUAGE`.

## API

### `POST /chat` — text path / WebSocket fallback (Req 4.3)
Request: `{ "message", "session_id?", "site?", "icp?", "page?" }`
Response: `{ text, ack, intent, persona, actions[], components[], grounding, session_id }`

### `WS /ws/voice?site=hirebuddha` — multiplexed voice transport
JSON envelopes: `{ channel, type, payload, sync_id, timestamp }` on channels
`AUDIO | DATA | EVENTS | STATE`. Client → server: `AUDIO/start|chunk|end`
(`end.payload.transcript` overrides ASR), `EVENTS/text`, `STATE/sync`,
`STATE/barge_in`. Server → client: `EVENTS/ready`, `AUDIO/*` (TTS),
`DATA/render|patch` (UI), `EVENTS/navigate|scroll_to|set_persona`,
`STATE/transcript`. **Correlated `DATA` + `AUDIO` share a `sync_id`** so the
frontend jitter buffer holds audio until its UI renders (Req 3.2.3/3.2.4).

## How it maps to the architecture

| Component | Code |
|---|---|
| Fast Router (intent/persona/ack) | `app/orchestrator/router.py` |
| Heavy Thinker (grounded reasoning + tools) | `app/orchestrator/thinker.py` |
| `query_cortex` + zero-hallucination guardrail | `app/cortex/query.py` |
| CORTEX bridge (ingest + cosine retrieval) | `app/cortex/bridge.py` |
| Gemini ↔ cortex provider adapters | `app/cortex/providers.py` |
| Vertex LLM / ASR / TTS engines | `app/ai/vertex.py` |
| Deterministic mock engines | `app/ai/mock.py` |
| Multiplexed WebSocket + barge-in | `app/transport/websocket.py` |
| Message envelope | `app/transport/envelope.py` |
| Ingestion pipeline (semantic scrape + DOM anchors) | `ingestion/` |

The framework targets 4 sites; each gets an isolated CORTEX knowledge tree keyed
by a deterministic per-site entity id (`app/config.py:site_entity_id`).
