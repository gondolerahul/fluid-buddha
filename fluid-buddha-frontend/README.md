# fluid-buddha-frontend

The multi-tenant **admin console** for Fluid-Buddha (Next.js 16 + React 19, App Router).
A tenant registers, logs in, and manages the voice agents running on their websites:

| Page | Path | Requirement |
|------|------|-------------|
| Register / Login | `/register`, `/login` | A — self-service auth (JWT bearer) |
| Dashboard | `/dashboard` | B — add & list websites |
| Ingestion | `/websites/[id]/ingestion` | C — upload/add data, run ingestion |
| Tour | `/websites/[id]/tour` | D — view, edit, regenerate the guided tour |
| Responses | `/websites/[id]/cache` | E + G — edit cached responses/actions; generated-vs-cached badges |
| Analytics | `/websites/[id]/analytics` | F + G — cost by ASR/TTS/Fast/Thinker/Tool, day/hour/session, performance, cache split |

## Run

```bash
cp .env.example .env.local       # point NEXT_PUBLIC_API_BASE at the backend (default :8080)
npm install
npm run dev                      # http://localhost:3001
```

The backend (`../backend`) must be running with the admin routes (auth/websites/
ingestion/tours/cache/analytics) and must allow `http://localhost:3001` in
`CORS_ORIGINS` (already the default). Start it with `cd ../backend && docker compose up -d --build`.

## Design

No Tailwind — a single hand-tuned design system lives in `src/app/globals.css`
(one accent, restrained palette, quiet motion). Charts use `recharts`. The typed
API client + JWT handling is in `src/lib/api.ts`; auth state in `src/lib/auth.tsx`.
