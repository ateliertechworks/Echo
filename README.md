# Echo

Echo is an AI-assisted team reporting system with two supported interfaces:

- A PySide6 desktop application backed by PostgreSQL and local Ollama.
- A React/Vite frontend with a Node.js/Express backend, PostgreSQL, and local Ollama.

Both interfaces use the same PostgreSQL schema and report workflow. No external
LLM API key is required.

## Full-stack quick start

Copy the environment template and edit the secrets before starting the stack:

```bash
cp .env.example .env
docker compose up --build
```

The services are then available at:

- Frontend: http://localhost:5173
- Backend: http://localhost:4000
- PostgreSQL: localhost:5432

Migrations run automatically when the backend starts. The database is bound to
`127.0.0.1` and is not exposed directly to the LAN.

Ollama runs on the host. Install it separately, start it, and download the model:

```bash
ollama pull qwen3:1.7b
```

The backend container reaches host Ollama through `host.docker.internal`. On
Linux, Ollama may need to listen beyond loopback:

```bash
sudo systemctl edit ollama
```

Add:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```

Then restart it:

```bash
sudo systemctl restart ollama
```

## Desktop quick start

```bash
cp .env.example .env
docker compose up -d db
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

The desktop application connects to PostgreSQL and runs migrations on startup.
If Ollama is unavailable, reports can still be entered and stored; the chat
falls back to lightly cleaned user text.

## Full-stack development without Docker

Start PostgreSQL with Docker, then use separate terminals for the backend and
frontend:

```bash
docker compose up db
```

```bash
cd backend
npm install
DATABASE_URL=postgres://teamreport:change-me-strong@localhost:5432/teamreport \
JWT_SECRET=dev-secret PORT=4000 npm run dev
```

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:4000 npm run dev
```

## Features

- Sign in and sign up with persistent sessions
- Profile setup with photo, social links, and skills
- Team creation, join codes, member roster, and leader controls
- Guided daily reports with follow-up questions and draft review
- Past report filtering and Excel export
- Local Ollama chatbot using `qwen3:1.7b`
- Responsive web interface and PySide6 desktop interface

## Project layout

```text
main.py                    PySide6 desktop entry point
launcher.py                Desktop first-launch setup
build_linux.sh             PyInstaller build script
Echo_Linux_Installer.sh    Desktop installer
backend/                   Node.js/Express API
frontend/                  React/Vite client
echo_app/                  PySide6 application source
docker-compose.yml         PostgreSQL, backend, and frontend services
echo_app/db/migrations/    Shared database migrations
echo_app/assets/           Desktop application assets
```

## Build the desktop executable

Install the Python requirements and PyInstaller in the virtual environment:

```bash
.venv/bin/pip install -r requirements.txt pyinstaller
./build_linux.sh
```

This creates `dist/Echo`. Build on Ubuntu for the Ubuntu/Linux architecture
where the executable will run.

## Release packaging

The release workflow for the one-command Ubuntu installer is documented in
[README_PACKAGING.md](README_PACKAGING.md). It creates the archive and checksum
file but does not upload or publish them.
