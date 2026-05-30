# FraudShield v3 — Enterprise Frontend

A modern, enterprise-grade fraud detection dashboard built with React 18, TypeScript, Vite, TailwindCSS, Zustand, and React Query.

---

## Tech Stack

| Layer | Library |
|---|---|
| Framework | React 18 + TypeScript |
| Build | Vite 5 |
| Styling | TailwindCSS 3 (dark/light, custom design tokens) |
| State | Zustand (auth + theme, persisted) |
| Data fetching | TanStack React Query v5 (caching, cancellation, optimistic updates) |
| Charts | Recharts |
| HTTP | Axios (with JWT interceptors + abort signal support) |
| Routing | React Router v6 |
| Icons | Lucide React |
| Toasts | React Hot Toast |
| Animation | Framer Motion |

---

## Folder Structure

```
fraudshield/
├── src/
│   ├── api/                  # HTTP service layer (one file per domain)
│   │   ├── client.ts         # Axios instance, JWT interceptors, cancellable helper
│   │   ├── auth.ts           # login, logout, getMe, changePassword, refresh
│   │   ├── fraud.ts          # transactions, predictions, alerts
│   │   ├── analytics.ts      # summary, trend, categories, merchants, health
│   │   ├── users.ts          # CRUD for user management
│   │   └── index.ts          # barrel re-export
│   │
│   ├── components/
│   │   ├── ui/               # Reusable design system components
│   │   │   ├── Badge.tsx     # StatusBadge + generic Badge
│   │   │   ├── Button.tsx    # variant/size/loading/icon
│   │   │   ├── Card.tsx      # Card, CardHeader, StatCard
│   │   │   ├── ErrorState.tsx# ErrorState + EmptyState
│   │   │   ├── Input.tsx     # Input, Select, Textarea
│   │   │   ├── Modal.tsx     # Accessible modal with keyboard trap
│   │   │   ├── Skeleton.tsx  # StatCardSkeleton, TableRowSkeleton, ChartSkeleton
│   │   │   ├── Table.tsx     # Table, Th, Tr, Td, Pagination, ScoreBar
│   │   │   └── index.ts      # barrel
│   │   │
│   │   ├── charts/           # Data visualisation components
│   │   │   ├── FraudTrendChart.tsx   # Area chart (safe/review/fraud over time)
│   │   │   ├── StatusDonut.tsx       # Pie donut + CategoryBar
│   │   │   └── index.ts
│   │   │
│   │   └── layout/           # App shell
│   │       ├── AppLayout.tsx # Sidebar + Topbar + main content
│   │       ├── Sidebar.tsx   # Collapsible nav with RBAC filtering
│   │       └── Topbar.tsx    # Breadcrumb, health status, theme toggle
│   │
│   ├── lib/
│   │   └── queryKeys.ts      # Typed React Query key factory
│   │
│   ├── pages/                # Route-level page components
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx     # KPI cards, trend chart, recent transactions
│   │   ├── LiveMonitor.tsx   # Auto-refreshing real-time feed
│   │   ├── Transactions.tsx  # Paginated table with search/filter + review modal
│   │   ├── Analytics.tsx     # Multi-chart analytics with range selector
│   │   ├── Cases.tsx         # Alert case management with resolution workflow
│   │   ├── Users.tsx         # User CRUD (admin only)
│   │   ├── Models.tsx        # ML model registry viewer
│   │   ├── Audit.tsx         # Audit log with search + pagination
│   │   ├── Settings.tsx      # Theme + password change
│   │   └── NotFound.tsx      # 404 page
│   │
│   ├── stores/               # Zustand global state
│   │   ├── authStore.ts      # User, tokens, RBAC can() helper (persisted)
│   │   ├── themeStore.ts     # Light/dark theme (persisted)
│   │   └── index.ts
│   │
│   ├── types/
│   │   └── api.ts            # All TypeScript interfaces (User, Transaction, etc.)
│   │
│   ├── utils/
│   │   └── format.ts         # cn(), formatCurrency, formatDate, formatPercent, etc.
│   │
│   ├── App.tsx               # Router + QueryClientProvider + auth guards
│   ├── main.tsx              # React root mount
│   └── index.css             # Tailwind directives + CSS vars
│
├── index.html
├── vite.config.ts            # @ alias to ./src, proxy /api → :8000
├── tailwind.config.js        # Custom design tokens (warm, navy, coral, sage, amber)
├── tsconfig.json
├── .env.example
└── package.json
```

---

## Getting Started

```bash
# 1. Install dependencies
npm install

# 2. Copy env file and set your backend URL
cp .env.example .env.local

# 3. Start dev server (proxies /api to :8000)
npm run dev

# 4. Build for production
npm run build
```

---

## Role-Based Access Control

Three roles are supported out of the box:

| Role | Access |
|---|---|
| `admin` | Full access — all pages, user management, model promotion |
| `analyst` | Dashboard, transactions, analytics, cases, live monitor |
| `auditor` | Dashboard, transactions, analytics, audit log (read-only) |

The `useAuthStore.can(permission)` helper gates both sidebar links and route-level navigation. Attempting to access a restricted route redirects to `/dashboard`.

---

## Key Patterns

### Request cancellation
Every React Query `queryFn` receives the `signal` from the query context and passes it to Axios via the config object. Navigating away from a page cancels in-flight requests automatically.

```ts
queryFn: ({ signal }) => getTransactions(filters, { signal })
```

### Optimistic updates
Mutations in `Transactions` and `Cases` pages use `onMutate` / `onError` / `onSettled` for instant UI feedback with automatic rollback on failure.

### API caching strategy
- Analytics summary: 30s stale, refetches every 60s
- Live monitor feed: refetches every 5s (pauseable)
- Health check: refetches every 30s
- Static data (models, users): 30s stale, no interval

### Dark / Light theme
Tailwind `darkMode: 'class'` — `themeStore` toggles the `dark` class on `<html>` and persists preference to `localStorage`.

---

## Design Tokens

The custom Tailwind palette:

| Token | Usage |
|---|---|
| `warm-*` | Light-mode backgrounds, borders |
| `navy-*` | Sidebar, dark-mode backgrounds, primary action |
| `coral-*` | Fraud, danger, primary CTA in dark mode |
| `sage-*` | Safe, success |
| `amber-*` | Review, warning |

Fonts: **Barlow Condensed** (display), **Barlow** (body), **DM Mono** (monospace/data).
