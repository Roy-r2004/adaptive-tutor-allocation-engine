# Apex AI Triage — Frontend

React + TypeScript SPA on top of the [`triage-pipeline`](../triage-pipeline) FastAPI backend.

Two surfaces:

- **`/`** — Chat surface. Submit a support message; watch it move through the 6-stage pipeline live (received → classifying → enriching → routing → resolved or awaiting_review).
- **`/reviewer`** — Reviewer dashboard for pending escalations. Accept, edit (override routing), or reject with a reason. Resolving any item resumes the paused LangGraph thread on the backend.
- **`/ticket/:id`** — Read-only deep view of any ticket's `FinalOutput` (classification, enrichment with source-quote highlighting, routing, escalation history).

## Stack

| Layer | Choice |
|---|---|
| Build | Vite 8 + React 19 + TypeScript (strict) |
| Styling | Tailwind v3 + custom CSS-variable design tokens (light + dark via `prefers-color-scheme`) |
| Primitives | shadcn/ui style (Radix under the hood) |
| State | TanStack Query v5 (no Redux, no Context for server state) |
| Validation | Zod schemas mirroring the backend's Pydantic models — every response is validated, malformed shapes throw `ApiSchemaError` |
| HTTP | Axios with one configured instance |
| Routing | React Router v6 |
| Motion | Framer Motion (out-expo `[0.16, 1, 0.3, 1]`, 150–300ms) |
| Tests | Vitest + Testing Library |

## Quick start

```bash
# Backend stack must be running on :8000 — see ../triage-pipeline/README.md
npm install
cp .env.example .env
npm run dev
# → http://localhost:5173
```

Or with the unified Docker stack from the parent directory:

```bash
cd ..
docker compose up -d --build
# → backend: http://localhost:8000
# → frontend: http://localhost:5173
# → reviewer dashboard: http://localhost:5173/reviewer
```

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | TypeScript project build + Vite production bundle |
| `npm run preview` | Serve the built bundle locally |
| `npm run lint` | ESLint over `src/` |
| `npm run test` | Vitest in watch mode |
| `npm run test:run` | Vitest single run (CI-friendly) |

## Project structure

```
src/
├── app/                          router shell + providers + page routes
│   ├── App.tsx
│   ├── providers.tsx             QueryClient + Toaster
│   └── routes/
│       ├── Chat.tsx              the main chat surface
│       ├── Reviewer.tsx          escalations dashboard
│       └── TicketDetail.tsx      /ticket/:id read-only deep view
│
├── components/
│   ├── chat/                     ChatThread, ChatComposer, MessageBubble,
│   │                             TicketStatusCard, FinalOutputCard, Sidebar
│   ├── reviewer/                 EscalationList, EscalationCard, EditRoutingDialog
│   ├── shared/                   CategoryBadge, PriorityIndicator, QueuePill,
│   │                             PipelineTimeline, EmptyState
│   └── ui/                       shadcn-style primitives (Button, Card, Dialog, …)
│
├── lib/
│   ├── api.ts                    axios instance + Zod-validated typed clients
│   ├── schemas.ts                Zod schemas — single source of truth, mirrors Pydantic
│   ├── queries.ts                TanStack Query hooks (polling, optimistic updates)
│   ├── format.ts                 date/duration/USD/ID formatters
│   └── utils.ts                  cn() helper
│
└── styles/globals.css            CSS variables + Tailwind directives
```

## Design notes

- **Asymmetric layout, not a centered ChatGPT-clone.** Fixed sidebar (≈320 px) on desktop, full-bleed chat on the right.
- **One accent + neutral 11-step gray.** Indigo accent, stone for everything else, semantic colors only for status (success / warning / danger).
- **Real status indicators.** Vertical timeline with connector lines, animated stage transitions, real outcome states. No horizontal progress bars with percentages.
- **Dense, confident typography.** Inter as sans (`-0.02em` on headings), JetBrains Mono for IDs / hashes / timestamps.
- **Subtle motion only.** Out-expo, 150–300ms. No bounces.

## Backend contract

| Method | Path | Used by |
|---|---|---|
| `POST` | `/v1/webhook/ingest` | `useIngestMessage` in `Chat.tsx` |
| `GET`  | `/v1/tickets/{id}` | `useTicket` (polls every 1 s until terminal status) |
| `GET`  | `/v1/escalations` | `usePendingEscalations` (refetches every 5 s) |
| `POST` | `/v1/escalations/{id}/resolve` | `useResolveEscalation` (optimistic remove on mutate) |
| `GET`  | `/healthz` | `useHealth` (sidebar status dot) |

Auth: `X-API-Key` header attached automatically when `VITE_API_KEY` is set. Backend's `INTERNAL_API_KEYS` defaults to empty, so dev runs unauthenticated.

## Tests

```
src/components/chat/__tests__/ChatComposer.test.tsx       # Cmd+Enter, empty submit, click send
src/components/reviewer/__tests__/EscalationCard.test.tsx # action wiring, reject-requires-reason
src/lib/__tests__/api.test.ts                             # Zod parsing rejects malformed shapes
```

Run with `npm run test:run`.
