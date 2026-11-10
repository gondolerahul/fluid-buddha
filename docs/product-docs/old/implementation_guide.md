# FluidBuddha: Implementation & Operations Guide

This guide provides step-by-step instructions for developers setting up, configuring, and operating **fluid-buddha** in both local development and production Google Cloud Vertex AI environments.

---

## 1. Local Development Quickstart

### Prerequisites
* **Docker & Docker Compose** (for containerized DB and API service).
* **Python 3.10+** (if running the backend locally outside Docker).
* **Node.js 18+ & npm** (for building the frontend SDK and Admin Panel).

### 1.1 Docker-Based Setup
The simplest way to run the entire backend stack (PostgreSQL with pgvector + FastAPI service) is via Docker Compose:

```bash
# Clone the repository and navigate to the backend directory
cd fluid-buddha/backend

# Build and start the containers in detached mode
docker compose up -d --build
```

This command starts:
1. **Database Container**: PostgreSQL + pgvector running on host port `5434` (internal container port `5432`).
2. **Backend API Container**: FastAPI orchestrator running on host port `8080`, with mock AI engines enabled by default (`MOCK_AI=true`).

#### Health Check Verification
Verify the service is active and running:
```bash
curl http://localhost:8080/readyz
# Expected output: {"status": "ok"}
```

---

## 2. Local Python Virtual Environment Setup

For developers modifying the FastAPI code, running the service within a Python virtual environment enables live reloading.

### 2.1 Dependencies Installation
```bash
cd fluid-buddha/backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install required dependencies
pip install -r requirements.txt

# Copy default environment variables template
cp .env.example .env
```

### 2.2 Environment Variables Config (`.env`)
By default, `.env` contains the following mock configurations:
```ini
MOCK_AI=true
CORTEX_DB_URL=postgresql+asyncpg://cortex:cortex@localhost:5434/cortex
FAST_MODEL=gemini-2.5-flash
HEAVY_MODEL=gemini-2.5-pro
EMBED_MODEL=text-embedding-004
LOG_LEVEL=INFO
```

### 2.3 Starting Database & Seeding Memory
To run the server locally, start PostgreSQL inside Docker and seed the knowledge database using the ingestion pipeline:

```bash
# Start PostgreSQL container
docker compose up -d postgres

# Ingest content for target sites (e.g., hirebuddha, fluidbuddha)
python -m ingestion.ingest --site hirebuddha
python -m ingestion.ingest --site fluidbuddha
```

### 2.4 Running Backend Server
```bash
# Run FastAPI server with auto-reload
uvicorn app.main:app --reload --port 8080
```

---

## 3. Frontend SDK Bundling & Demo Run

### 3.1 Installation & Compiling
```bash
cd fluid-buddha/fluid-buddha-sdk

# Install npm packages
npm install

# Run TypeScript typechecks
npm run typecheck

# Compile the packages
npm run build
```
The compiled output is written to the `dist/` folder.

### 3.2 Running the Live Demo
You can try the SDK against your local API service using the built-in demo environment:
```bash
# Starts a local server on http://localhost:4000
npm run serve:demo
```
Open a browser and navigate to `http://localhost:4000` to interact with Pragya.

---

## 4. Going Live on Vertex AI (Google Cloud Platform)

To deploy fluid-buddha using live Vertex AI models instead of deterministic mocks, perform the following steps:

### 4.1 GCP Authentication
Authorize application default credentials locally:
```bash
gcloud auth application-default login
```

### 4.2 Production Environment Config (`.env`)
Modify your `.env` file to disable mock models and reference your active GCP project:
```ini
MOCK_AI=false
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
VERTEX_LOCATION=us-central1
CORTEX_DB_URL=postgresql+asyncpg://db_user:db_password@prod-db-ip:5432/cortex
```

### 4.3 Re-indexing Vector Databases
Since Vertex AI uses `text-embedding-004` (768 dimensions) to calculate embeddings, you must re-run the ingestion script after switching `MOCK_AI` to `false`:
```bash
# Re-index content using live embeddings API
python -m ingestion.ingest --site hirebuddha
```

---

## 5. Integrating fluid-buddha on a Target Site

### 5.1 One-Line Integration
Insert the global script bundle within the target website's layout template:

```html
<script src="https://cdn.yourdomain.com/fluid-buddha.global.js"
        data-backend="wss://voice.yourdomain.com"
        data-site="hirebuddha"
        data-accent="#c9a24a"
        data-intelligence="advance"
        data-design="level1"></script>
```

### 5.2 Programmatic Integration (Single Page Apps)
For SPAs using routers (e.g., Next.js, React Router, Vue Router), import the initialization function programmatically:

```typescript
import { init } from 'fluid-buddha';

const overlay = init({
  backend: 'wss://voice.yourdomain.com',
  site: 'my-saas-platform',
  intelligence: 'advance',
  design: 'level3',
  hooks: {
    // Intercept redirects to route inside React/Next.js
    onNavigate: (path: string) => {
      router.push(path);
    },
    // Intercept scroll events
    onScrollTo: (target) => {
      if (target.sectionId) {
        document.getElementById(target.sectionId)?.scrollIntoView({ behavior: 'smooth' });
      }
    },
    // Intercept user segment persona switches
    onSetPersona: (persona: string) => {
      console.log(`Silent persona change detected: ${persona}`);
      setAppTheme(persona);
    }
  }
});
```

### 5.3 Listening to Window Custom Events
If you want to track interactions from separate scripts outside of programmatic hook callbacks, you can register listeners on the global `window` object:

```javascript
window.addEventListener('fluidbuddha:navigate', (e) => {
  console.log('User navigated by Pragya to:', e.detail.path);
});

window.addEventListener('fluidbuddha:set_persona', (e) => {
  console.log('Visitor classified under segment:', e.detail.persona);
});
```

---

## 6. Performance Optimization: Three.js Dynamic Bundling

> [!TIP]
> The compiled IIFE bundle sizes differ significantly based on dependencies.

* **Base Size (Level 1 & Level 3)**: ~120 kB minified (~35 kB gzipped). These tiers utilize dependency-free 2D canvas routines.
* **Full Size (Level 2 Immersive Mode)**: ~590 kB minified (~155 kB gzipped) because **Three.js** is compiled in.

### Bundle Size Strategy
To optimize initial page load times, compile the SDK to dynamically import Three.js only when the configuration file sets `design: 'level2'`. This keeps the initial IIFE bundle lightweight for sites using only the sidebar companion or edge-aura interfaces.
