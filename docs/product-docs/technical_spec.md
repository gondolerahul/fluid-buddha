# Fluid-Buddha: Technical Specification

This document details the software architecture, communications protocol, data schemas, and backend configurations that make up the **fluid-buddha** system.

---

## 1. System Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Web Browser (Client)                          │
│                                                                        │
│  ┌──────────────────────┐               ┌───────────────────────────┐  │
│  │   Host Website DOM   │               │   fluid-buddha SDK        │  │
│  │                      │               │   (Shadow DOM)            │  │
│  │  Custom Events ◄─────┼───────────────┼── HostBridge              │  │
│  │  CSS data-attrs ◄────┼───────────────┼── Playout Jitter Buffer   │  │
│  │                      │               │   Generative UI Canvas    │  │
│  │  Web Speech API ─────┼───────────────┼──►AudioCapture + VAD      │  │
│  └──────────────────────┘               └──────┬────────────▲───────┘  │
└────────────────────────────────────────────────┼────────────│──────────┘
                                                 │            │
                                 Multiplexed WS  │            │  TTS PCM /
                                 Audio & State   │            │  UI Data
                                                 ▼            │
┌─────────────────────────────────────────────────────────────┴──────────┐
│                           Backend Service                              │
│                                                                        │
│  ┌───────────────────────────────┐     ┌────────────────────────────┐  │
│  │  FastAPI Transport Endpoint   │     │    Cognitive Loop Manager  │  │
│  │                               │     │                            │  │
│  │  • WS Multiplexer             ├────►│    • Fast Router (Flash)   │  │
│  │  • Text /chat Fallback        │     │    • Heavy Thinker (Pro)   │  │
│  └───────────────────────────────┘     └─────────────┬──────────────┘  │
│                                                      │                 │
│                                                      ▼                 │
│                                        ┌────────────────────────────┐  │
│                                        │  CORTEX Vector Engine      │  │
│                                        │                            │  │
│                                        │  • pgvector Semantic Match │  │
│                                        │  • Episodic Cache / Replay │  │
│                                        └────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Frontend SDK Architecture

The Frontend SDK is written in TypeScript and compiled into three outputs:
* `dist/fluid-buddha.global.js`: IIFE version for one-line `<script>` tags, exposing `window.FluidBuddha`.
* `dist/fluid-buddha.mjs`: ES module for modern bundle bundlers (e.g., Vite/Webpack).
* `dist/fluid-buddha.cjs`: CommonJS module for backward compatibility.

### 2.1 Playout Jitter Buffer & Synchronization
Due to network latency and server rendering speeds, generative UI layout data and synthesized Text-to-Speech (TTS) audio may arrive out of sequence. The SDK resolves this using a **Jitter Buffer** (`src/audio/JitterBuffer.ts`):
* **Sync IDs**: The server associates matching audio chunks (`AUDIO` channel) and UI layouts (`DATA` channel) with a shared `sync_id`.
* **Playout Lock**: The Jitter Buffer blocks playout of the synthesized voice until the corresponding UI card is successfully compiled and renders to the DOM.
* **Filler Audio**: If the layout rendering delay exceeds `ui_filler_delay_ms` (default: `1500ms`), the Jitter Buffer plays a brief acoustic "filler" or subtle background hum to maintain fluid conversation.

### 2.2 Host Bridge & Fuzzy DOM Interaction
The Host Bridge (`src/core/HostBridge.ts`) manages DOM interactions outside of the Shadow DOM boundary without requiring hard-coded selectors:
* **Fuzzy Scrolling**: When the agent requests a scroll to an element (e.g., `#pricing`), the bridge searches the page for the ID, then scans for partial matches, and finally searches heading elements (`h1`, `h2`, `h3`, `h4`) containing the text.
* **Event Dispatching**: Every navigation, scrolling, or persona command emits a `fluidbuddha:*` `CustomEvent` on `window`, allowing host SPAs to intercept and handle actions programmatically.
* **Crossfade Veil**: During persona swaps, a full-screen `div[data-fb-persona-veil]` with a 2px backdrop-filter blur and 40% opacity fades in over 150ms. The DOM layout changes at peak opacity, and the veil fades out over 150ms, preventing visual layout flashing.

### 2.3 Generative UI Layout Compiler
The renderer canvas (`src/ui/components/canvas.ts`) compiles raw JSON payloads into responsive visual widgets. 

#### Supported Renderers
1. `flowchart`: Draws logic flows using SVG paths.
2. `workflow`: Renders standard processes.
3. `component_diagram`: Visualizes system architectures.
4. `graph` & `chart`: Render plots using lightweight charting wrappers.
5. `roi_calculator`: Evaluates equations locally using interactive inputs.
6. `comparisonTable`: Builds responsive checklists and price grids.
7. `mind_map`: Interactive multi-node maps.
8. `configurator`: Step-by-step parameter choices.
9. `sankey`: Renders flow diagrams.
10. `scenario_simulator`: Local simulator showing changes across variable scopes.

### 2.4 Sandbox-Safe Arithmetic Evaluator (`evalExpr`)
To allow dynamic calculation cards (like ROI calculators) without executing unsafe code, the SDK contains a custom parser (`src/ui/components/interactive.ts`):
* The engine tokenizes mathematical strings like `(seats * monthly_cost) - savings`.
* Converts expressions into **Reverse Polish Notation (RPN)** using the Shunting-yard algorithm.
* Evaluates variables safely within a sandbox. This removes the need for `eval()` or `new Function()`, mitigating remote code execution (RCE) risks from malicious payloads.

---

## 3. Communication Protocol (Multiplexed WebSockets)

The primary channel is `WS /ws/voice?site={site_key}&intelligence={intelligence_level}&design={design_level}`. Messages are JSON envelopes structured as follows:

```json
{
  "channel": "AUDIO | DATA | EVENTS | STATE",
  "type": "string",
  "payload": {},
  "sync_id": "string",
  "timestamp": 1719665700
}
```

### 3.1 Client-to-Server Envelopes

| Channel | Type | Payload Attributes | Description |
| :--- | :--- | :--- | :--- |
| **AUDIO** | `start` | `{ "session_id": "string" }` | Indicates that the user has started speaking. |
| **AUDIO** | `chunk` | `{ "data": "base64_pcm" }` | Raw 16kHz 16-bit Mono PCM audio chunks. |
| **AUDIO** | `end` | `{ "transcript": "string" }` | Audio stream complete. Contains client-side ASR transcripts if available. |
| **STATE** | `sync` | `{ "page": "/pricing", "viewport": "#faq" }` | Periodically synchronizes viewport locations and active sections. |
| **STATE** | `barge_in` | `{}` | Sent immediately when the client detects user speech during agent output. |

### 3.2 Server-to-Client Envelopes

| Channel | Type | Payload Attributes | Description |
| :--- | :--- | :--- | :--- |
| **EVENTS** | `ready` | `{ "sample_rate": 24000, "filler_delay_ms": 1500 }` | Sent on connection. Confirms server status. |
| **AUDIO** | `start` | `{ "text": "spoken_response", "grounding": {} }` | Prepares the Jitter Buffer for incoming TTS voice output. |
| **AUDIO** | `chunk` | `{ "data": "base64_pcm" }` | Base64-encoded 24kHz PCM audio chunks. |
| **AUDIO** | `end` | `{}` | Synthesized speech output complete. |
| **DATA** | `render` | `{ "component_type": "roi_calculator", "initial_state": {} }` | Generates a new component card on the client. |
| **DATA** | `patch` | `{ "target_sync_id": "string", "patch": {} }` | Updates values in an active generative UI card. |
| **EVENTS** | `navigate` | `{ "path": "/dashboard" }` | Instructs the host site to navigate. |

---

## 4. Backend Cognitive Loop Architecture

The Python backend uses FastAPI to route requests. It processes tasks through a dual-model cognitive loop (`app/orchestrator/loop.py`):

```
                       [User Utterance]
                               │
                               ▼
               ┌──────────────────────────────┐
               │    Fast Router (Flash)       │
               │                              │
               │  • Immediate Acknowledgment  │
               │  • Persona Classification    │
               └───────────────┬──────────────┘
                               │
                       Is complex logic /
                     diagram/tool needed?
                               │
                       ┌───────┴───────┐
                       ▼               ▼
                     [Yes]            [No]
                       │               │
        ┌──────────────┴──────┐ ┌──────┴──────────────┐
        │ Heavy Thinker (Pro) │ │ Lean Responder      │
        │                     │ │                     │
        │  • Tool Executions  │ │ • Vector Retrieval  │
        │  • pgvector Ground  │ │ • Single LLM Pass   │
        │  • Page Composers   │ └─────────────────────┘
        └─────────────────────┘
```

### 4.1 Fast Router (`app/orchestrator/router.py`)
* **Model**: powered by `gemini-2.5-flash`.
* **Latency**: ~150-300ms.
* **Role**: Parses user inputs, generates immediate spoken acknowledgments (e.g., "Sure, let me fetch that layout for you..."), classifies user intent, and determines target visitor personas.

### 4.2 Heavy Thinker (`app/orchestrator/thinker.py`)
* **Model**: Powered by `gemini-2.5-pro`.
* **Latency**: ~1.5 - 3.5s.
* **Role**: Executes the core cognitive reasoning. It uses tool calls to query site databases, retrieve documentation, compose diagrams, and build pages.

### 4.3 CORTEX Knowledge Vector Engine (`app/cortex/`)
Every target site holds a separate knowledge segment in the database, isolated using deterministic entity UUIDs:
* **Embeddings**: Text blocks are embedded into 768-dimension vectors using `text-embedding-004`.
* **Retrieval Similarity**: Queries use cosine similarity searches. Results below the `cortex_confidence_threshold` (default: `0.45`) are ignored.
* **Episodic Replay Cache**: Frequently asked questions are cached along with their visual layouts and TTS audio files. If a new user query matches a cached question with a cosine similarity score `>= 0.92`, the system skips the cognitive loop and replays the cached audio and layout instantly.

---

## 5. Admin Dashboard Architecture

The multi-tenant admin dashboard (`fluid-buddha-frontend`) is built using Next.js 16 and React 19 (App Router). It enables tenants to configure, monitor, and train their voice agents.

### 5.1 Dashboard Pages

```
/dashboard
├── /websites
│   └── /[id]
│       ├── /ingestion    <-- Document uploads and pgvector parser triggers
│       ├── /tour         <-- Interactive guided tour editor
│       ├── /cache        <-- Conversation cache & Episodic replay matches
│       └── /analytics    <-- ASR, TTS, and LLM cost tracking
```

* **Authentication (`/login`, `/register`)**: Self-service user sign-ups secured with JWT bearer tokens.
* **Ingestion Portal (`/websites/[id]/ingestion`)**: Uploads text files, PDF documents, and site maps, chunking them into the pgvector database.
* **Tour Editor (`/websites/[id]/tour`)**: Edits paths, steps, scroll targets, and narrations for automated tours.
* **Conversation Cache Editor (`/websites/[id]/cache`)**: Tracks hits and misses in the Episodic memory cache, allowing administrators to edit answers and manually approve cached items.
* **Analytics Console (`/websites/[id]/analytics`)**: Tracks API token usage, model execution times, and cache hit ratios.
