# VSCode Run Guide

## First Open

Open `/Users/zluo/Project/STS` as the workspace folder in VSCode.

Install the recommended extensions when VSCode asks:

- Python
- Python Debugger
- Pylance
- Vue - Official
- ESLint

## One-Time Setup

If dependencies are already installed, you can skip this section.

Run these from `Terminal > Run Task...`:

1. `Setup: backend venv`
2. `Setup: frontend deps`

The backend task creates `backend/.venv` and installs FastAPI, pytest, and related packages. The frontend task installs Vite and Vue dependencies in `frontend/node_modules`.

## Run The App

Use `Run and Debug` in VSCode and select:

- `Run: STS full stack`

This starts:

- Backend API: `http://127.0.0.1:8000`
- Frontend site: `http://127.0.0.1:5173`

Open `http://127.0.0.1:5173` in the browser.

If VSCode reports `ModuleNotFoundError: No module named 'fastapi'`, it is using the system Python instead of `backend/.venv`.

Fix it by selecting:

1. `Command Palette > Python: Select Interpreter`
2. Choose `/Users/zluo/Project/STS/backend/.venv/bin/python`
3. Run `Run: STS full stack` again

## Run Only One Side

From `Terminal > Run Task...`:

- Backend only: `Run: backend API`
- Frontend only: `Run: frontend Vite`

From `Run and Debug`:

- Backend debug: `Debug: backend FastAPI`
- Frontend dev server: `Run: frontend Vite`

## Tests

From `Terminal > Run Task...`:

- Backend tests: `Test: backend`
- Frontend tests: `Test: frontend`
- Frontend production build: `Build: frontend`

## Database

The backend reads `backend/.env`. That file is intentionally not committed. Keep your local MySQL URL and JWT secret there.

The committed `backend/.env.example` only shows the expected variable names.
