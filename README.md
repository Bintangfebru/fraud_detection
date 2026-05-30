# FraudShield

Full-stack fraud detection system built with a Python/FastAPI backend and a React/TypeScript frontend. Designed for real-time transaction monitoring, machine learning-powered risk scoring, and role-based operational control.

---

## Overview

FraudShield  is a production-oriented platform that combines a high-performance REST + WebSocket API, an ML ensemble pipeline, real-time event streaming via Kafka and Redis.

---

### Screenshots
![Main Dashboard](img/ss.png)


## Project Structure

```
fraudshield v4/
├── backend/                        # Python — FastAPI + SQLAlchemy + ML
│   ├── app/
│   │   ├── api/                    # Route handlers and dependency injection
│   │   │   └── v1/                 # Versioned API endpoints
│   │   │       ├── analytics.py    # Analytics endpoints
│   │   │       ├── audit.py        # Audit log endpoints
│   │   │       ├── auth.py         # Authentication endpoints
│   │   │       ├── fraud.py        # Fraud detection endpoints
│   │   │       ├── models.py       # ML model management endpoints
│   │   │       ├── streaming.py    # WebSocket streaming endpoints
│   │   │       └── users.py        # User management endpoints
│   │   ├── config/                 # Application settings and database config
│   │   ├── core/                   # Security, Redis client, exceptions, logging
│   │   ├── db/                     # Session management, base models, DB init
│   │   ├── middleware/             # Correlation ID injection, exception handling
│   │   ├── ml/                     # ML pipeline modules
│   │   │   ├── anomaly_detector.py # Anomaly detection logic
│   │   │   ├── auto_retrain.py     # Automated model retraining
│   │   │   ├── drift_detector.py   # Model drift monitoring
│   │   │   ├── ensemble.py         # Ensemble model orchestration
│   │   │   ├── explainability.py   # SHAP-based model explanations
│   │   │   ├── feature_engineering.py  # Feature extraction
│   │   │   ├── feature_store.py    # Feature caching and retrieval
│   │   │   ├── graph_analyzer.py   # Graph-based fraud ring detection
│   │   │   ├── model_versioning.py # Model version control and registry
│   │   │   ├── observability.py    # ML metrics and monitoring
│   │   │   └── predictor.py        # Inference pipeline
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── repositories/           # Data access layer
│   │   ├── routes/                 # Health, analytics, fraud routes
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   ├── services/               # Business logic layer
│   │   ├── streaming/              # WebSocket manager, Kafka, Redis pub/sub
│   │   └── utils/                  # Helpers, validators, logger
│   ├── migrations/                 # Alembic database migrations
│   ├── scripts/                    # Database initialization SQL
│   ├── tests/                      # Pytest test suites
│   ├── trained_models/             # Serialized ML pipeline (.pkl)
│   ├── main.py                     # FastAPI application entry point
│   ├── requirements.txt
│   ├── start.sh
│   └── .env
│
├── frontend/                       # React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── api/                    # Axios service layer (auth, fraud, analytics, users)
│   │   ├── components/
│   │   │   ├── charts/             # Recharts wrappers (FraudTrendChart, StatusDonut)
│   │   │   ├── layout/             # AppLayout, Sidebar, Topbar
│   │   │   └── ui/                 # Button, Card, Badge, Input, Table, Modal, Skeleton
│   │   ├── lib/                    # React Query key factory
│   │   ├── pages/                  # 10 route-level page components
│   │   ├── stores/                 # Zustand stores — auth (RBAC) + theme
│   │   ├── types/                  # Shared TypeScript interfaces
│   │   ├── utils/                  # Formatting utilities (currency, date, classnames)
│   │   ├── App.tsx                 # Router + QueryClientProvider + auth guards
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts              # Path alias + /api proxy to :8000
│   ├── tailwind.config.js
│   └── tsconfig.json
│
└── deployment/                     # Docker + Nginx
    ├── docker-compose.yml
    ├── Dockerfile
    └── nginx.conf
```

---

## Tech Stack

### Languages

| Language | Role |
|---|---|
| Python 3.11 | Backend API, ML pipeline, database migrations, tests |
| TypeScript 5 | Frontend application, type-safe API contracts |
| SQL | Database schema, Alembic migrations |
| Bash | Startup scripts, automation |

### Backend

| Library / Tool | Version | Purpose |
|---|---|---|
| FastAPI | 0.111.0 | ASGI web framework REST API and WebSocket endpoints |
| Uvicorn | 0.29.0 | ASGI server with hot-reload support |
| SQLAlchemy | 2.0.30 | ORM and async database engine |
| asyncpg | 0.29.0 | Async PostgreSQL driver |
| psycopg2-binary | 2.9.9 | Sync PostgreSQL driver (Alembic + training thread) |
| Alembic | 1.13.1 | Database schema migration management |
| Redis (asyncio) | 5.0.4 | Async caching, pub/sub messaging |
| PyJWT | 2.8.0 | JWT token encoding and decoding |
| bcrypt | 4.1.3 | Password hashing (work factor 12) |
| python-jose | 3.3.0 | Cryptographic utilities for auth |
| Pydantic v2 | 2.7.1 | Request/response data validation and serialization |
| pydantic-settings | 2.3.0 | Environment-based configuration via .env |
| scikit-learn | 1.6.1 | ML ensemble models (RandomForest, IsolationForest, etc.) |
| NumPy | 1.26.4 | Numerical computation |
| Pandas | 2.2.2 | Data manipulation and feature engineering |
| joblib | 1.4.2 | ML model serialization and parallel processing |
| aiokafka | 0.10.0 | Async Kafka producer/consumer for event streaming |
| websockets | 12.0 | WebSocket protocol support |
| python-json-logger | 2.0.7 | Structured JSON logging |
| pytest + pytest-asyncio | 8.2.0 | Unit, integration, and async test suites |
| httpx | 0.27.0 | Async HTTP client for tests and health checks |

### Frontend

| Library / Tool | Version | Purpose |
|---|---|---|
| React | 18.3.1 | UI component framework |
| TypeScript | 5.x | Static typing across the entire frontend |
| Vite | 5.3.2 | Build tooling with HMR and path aliasing |
| TailwindCSS | 3.4.6 | Utility-first CSS with custom design tokens |
| TanStack React Query | 5.45.1 | Server state management, caching, and background refetch |
| Zustand | 4.5.4 | Lightweight client state (auth session, theme) |
| React Router | 6.23.1 | Client-side routing with protected routes |
| Axios | 1.7.2 | HTTP client with JWT interceptors and abort signals |
| Recharts | 2.12.7 | Chart library for trend and distribution visualizations |
| Framer Motion | 11.3.2 | UI animations and transitions |
| Lucide React | 0.395.0 | Icon library |
| react-hot-toast | 2.4.1 | Toast notification system |
| date-fns | 3.6.0 | Date formatting and manipulation |
| ESLint + TypeScript ESLint | 8.x / 7.x | Code linting and type-aware static analysis |

### Infrastructure

| Tool | Purpose |
|---|---|
| PostgreSQL 15+ | Primary relational database |
| Redis 7+ | Caching layer, pub/sub event bus |
| Apache Kafka | Real-time transaction event streaming |
| Docker + Docker Compose | Containerization and local multi-service orchestration |
| Nginx | Reverse proxy and static file serving |

---

## Architecture

```
┌─────────────────────────────────────────┐
│         React / TypeScript SPA          │
│    Vite · TanStack Query · Zustand      │
└──────────────────┬──────────────────────┘
                   │ HTTP / WebSocket
┌──────────────────▼──────────────────────┐
│           FastAPI Backend               │
│    SQLAlchemy · Pydantic v2 · JWT       │
└──────┬───────────┬──────────┬───────────┘
       │           │          │
┌──────▼──────┐ ┌──▼──────┐ ┌─▼───────────┐
│ PostgreSQL  │ │  Redis  │ │    Kafka    │
│   asyncpg   │ │ Cache · │ │  Streaming  │
│   Alembic   │ │ pub/sub │ │   aiokafka  │
└─────────────┘ └─────────┘ └──────┬──────┘
                                   │
                        ┌──────────▼──────────┐
                        │     ML Pipeline     │
                        │  Ensemble · SHAP    │
                        │  Feature Store      │
                        │  Drift Detector     │
                        └─────────────────────┘
```

The backend exposes a versioned REST API at `/api/v1/` and a WebSocket endpoint for live transaction feeds. The ML pipeline runs as an in-process service predictions are synchronous with the request cycle while model retraining and drift detection run as background tasks.

---

## Core Features

### Machine Learning Pipeline

- Ensemble model combining RandomForest, IsolationForest, and Logistic Regression, trained and serialized as a single scikit-learn pipeline
- Real-time feature engineering with a dedicated feature store layer for caching computed features
- SHAP based explainability every prediction includes a breakdown of contributing factors
- Automated drift detection that monitors input distribution and model performance over time
- Scheduled auto-retraining triggered when drift thresholds are breached

### Real-Time Streaming

- Kafka producer and consumer for high-throughput transaction event ingestion
- Redis pub/sub for low-latency internal message passing
- WebSocket connection manager for pushing live fraud alerts to connected dashboard clients

### Authentication and Authorization

- JWT-based authentication with bcrypt password hashing
- Role-based access control with three roles: `admin`, `analyst`, and `auditor`
- Per-role page access and API permission scoping

| Role | Access |
|---|---|
| admin | All pages including User Management and Model Manager |
| analyst | Dashboard, Live Monitor, Transactions, Analytics, Cases |
| auditor | Dashboard, Transactions, Analytics, Audit Log (read-only) |

### Risk Scoring

- Continuous risk score from 0.0 to 1.0 per transaction
- Five risk categories: MINIMAL (0.0-0.2), LOW (0.2-0.4), MEDIUM (0.4-0.6), HIGH (0.6-0.8), CRITICAL (0.8-1.0)
- Three decision outcomes: APPROVED, REVIEW, DECLINED

### Dashboard Pages

| Page | Description |
|---|---|
| Dashboard | Summary metrics — active alerts, transaction volume, fraud rate |
| Live Monitor | Real-time WebSocket feed of incoming transactions |
| Transactions | Paginated transaction list with search and filters |
| Analytics | Trend charts, risk distribution, time-of-day patterns |
| Cases | Fraud case management and investigation workflow |
| Models | ML model performance metrics, version history, retraining controls |
| Audit Log | Immutable log of all system and user actions |
| Users | User account management (admin only) |
| Settings | System configuration and threshold tuning |

---

## Service Access

| Service | URL | Description |
|---|---|---|
| FastAPI Backend | http://localhost:8000 | REST API |
| API Documentation | http://localhost:8000/docs | Interactive Swagger UI |
| React Frontend | http://localhost:5173 | Development server |
| PostgreSQL | localhost:5432 | Primary database |
| Redis | localhost:6379 | Cache and pub/sub |

---

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env .env.local              # Fill in DB, Redis, and secret values
alembic upgrade head            # Run all migrations
uvicorn main:app --reload       # API starts on :8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local      # Set VITE_API_BASE=http://127.0.0.1:8000
npm run dev                     # Dev server starts on :5173, proxies /api to :8000
```

### Docker (full stack)

```bash
docker compose -f deployment/docker-compose.yml up --build
```

---

## Environment Variables

```bash
# Backend (.env)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/fraudshield
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key
APP_ENV=development
APP_VERSION=4.0.0

# Frontend (.env.local)
VITE_API_BASE=http://127.0.0.1:8000
```

---

## Testing

```bash
cd backend
pytest                          # All tests
pytest tests/test_api.py        # API tests only
pytest tests/test_model.py      # ML model tests only
pytest --cov=app tests/         # With coverage report
```

---

## Design Tokens

The frontend uses a custom Tailwind token system defined in `tailwind.config.js`:

| Token | Usage |
|---|---|
| `warm-*` | Light-mode backgrounds and borders |
| `navy-*` | Sidebar and dark-mode backgrounds |
| `coral-*` | Fraud alerts, danger states, primary CTA (dark mode) |
| `sage-*` | Safe and success states |
| `amber-*` | Review and warning states |

Fonts: Barlow Condensed (display headings) Barlow (body text) DM Mono (data and monospace fields)

---

## Strengths and Trade-offs

### Strengths

- **Clean separation of concerns** 
the repository enforces a strict layered architecture: routes handle HTTP, services own business logic, repositories own data access, and ML modules are isolated from the web layer. Each layer is independently testable.
- **Type safety end-to-end** 
Pydantic v2 schemas on the backend and TypeScript interfaces on the frontend mean that API contracts are enforced at both boundaries, reducing runtime errors from data shape mismatches.
- **Real-time capable**
 the combination of WebSockets, Kafka, and Redis pub/sub gives the system multiple paths for real-time data delivery depending on throughput and latency requirements.
- **Explainable ML** 
SHAP integration means every fraud prediction can be traced to specific features, which is critical for compliance and analyst trust.
- **Async throughout** 
FastAPI, asyncpg, and the Redis asyncio client are all non-blocking, keeping the backend responsive under concurrent load without thread-per-request overhead.
- **Observability built in** 
structured JSON logging, correlation ID middleware for request tracing, drift detection, and a dedicated observability module mean the system is designed to be monitored in production, not retrofitted.

### Trade-offs and Limitations

- **Single-process ML** 
model inference runs in-process with the API. Under very high load, CPU-intensive prediction could compete with request handling. A dedicated inference service (e.g., a separate worker with a task queue) would improve isolation.
- **No message broker required at startup** 
Kafka is optional and falls back to Redis; this simplifies local development but means the streaming architecture behaves differently in development vs. production until Kafka is explicitly configured.
- **Frontend has no end-to-end tests** 
the test suite covers backend API and ML layers but does not include Playwright or Cypress tests for the React frontend. UI regressions rely on TypeScript compilation and linting rather than behavioral tests.
- **Single database** 
the current schema uses PostgreSQL for both transactional records and audit logs. At scale, separating these into distinct stores (e.g., append-only audit to a time-series database) would improve write throughput and query isolation.
- **Trained model is file-based** 
the ML pipeline is persisted as a `.pkl` file on disk. In a multi-instance deployment, this requires a shared volume or an artifact store to ensure all replicas load the same model version.

---

## License

MIT License
