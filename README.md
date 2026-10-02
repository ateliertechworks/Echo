# AI Team Report Management System

Full-stack PWA for AI-assisted team daily reporting. React + Vite frontend, Node.js/Express backend, PostgreSQL, fully Dockerized.

## Quick start

```bash
cp .env.example .env
# edit .env if needed
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend:  http://localhost:4000
- Postgres: localhost:5432

Migrations run automatically on backend startup.

The report chatbot ("Echo") uses a local Ollama model — no external API keys. Install it once with `ollama pull qwen3:1.7b`.
The backend container reaches Ollama on the host via `host.docker.internal`, so Ollama must listen beyond loopback:

```bash
sudo systemctl edit ollama   # add:  [Service]  Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl restart ollama
```

If the model is offline, the chatbot still works: answers are stored as typed (lightly cleaned) and the header shows "model offline".

## Development (without Docker)

```bash
# Terminal 1 — start postgres via docker
docker compose up db

# Terminal 2 — backend
cd backend
npm install
DATABASE_URL=postgres://teamreport:change-me-strong@localhost:5432/teamreport \
JWT_SECRET=dev-secret PORT=4000 npm run dev

# Terminal 3 — frontend
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:4000 npm run dev
```

## Features

- Split-screen Sign In / Sign Up with team-photo hero
- Profile setup with social links, photo, skills
- Team creation (auto-leader) & join by code
- Team workspace with three tabs: Today's Report, Past Reports, Team Details
- Scripted chatbot flows for leader (with discussion) and member
- Filtered Excel export — one sheet per person, leader's first
- Installable PWA (manifest + service worker)
- Responsive: mobile-first, works at 375px / 768px / 1440px+
