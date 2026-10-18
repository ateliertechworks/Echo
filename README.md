# Echo — AI Team Report (desktop)

A PySide6 desktop app for AI-assisted daily team reporting. Each teammate runs the app; everyone's
reports go to one shared PostgreSQL database. The report chatbot ("Echo") uses a local Ollama model, so
there are no external API keys.

## Quick start

```bash
cp .env.example .env              # edit if needed
docker compose up -d db           # shared Postgres
ollama pull qwen3:1.7b            # chatbot model (optional, see below)

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py          # or: python -m echo_app
```

Database migrations run automatically every time the app starts.

If Ollama or the model isn't available, Echo still works: answers are stored as typed (lightly cleaned) and
the chat header shows "model offline".

## Team setup

Run Postgres on one machine (or use a managed Postgres) and set `DATABASE_URL` in each teammate's `.env`
to point at it, e.g. `postgresql://teamreport:<password>@192.168.1.20:5432/teamreport`.
The app connects to the database directly, so every install holds the database credentials. Only share
them with your team, and use a strong `POSTGRES_PASSWORD`.

## Build a standalone app

```bash
./build.sh                        # creates dist/Echo/
```

Build on each target OS (Linux, Windows, macOS). Put a `.env` next to the `Echo` executable to configure it.

## Features

- Sign in / sign up, remembered between launches
- Profile setup with photo, social links and skills
- Teams: create (you become leader), join by code, member roster, remove members (leader)
- Today's Report: Echo asks one question at a time, tidies answers, fills several fields from one reply, asks
  follow-ups on vague answers and remembers yesterday's project. It shows a live draft and an editable preview,
  and nothing is saved until you click Save Report. Drafts survive app restarts.
- Past Reports: filter by month, year, date or range, and by member (leader)
- Excel export, one sheet per person with the leader first. Members export only their own sheet.

## Project layout

```
main.py                    entry point
echo_app/
  config.py                .env / environment settings
  db/                      connection pool + SQL migrations
  services/                auth, profile, teams, reports, Excel export, chatbot (chat_flow, model, memory)
  ui/                      PySide6 windows, pages, theme and widgets
  assets/                  icons and artwork
```
## to run the file everytime
docker compose up -d db
.venv/bin/python main.py