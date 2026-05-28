# @capsulelab/frontend

CapsuleLab's React dashboard for managing local projects, runtimes, apps, locations, and settings.

## Setup

```bash
npm install
```

## Development

```bash
npm run dev
```

Starts the dashboard on `http://localhost:5173`. The development proxy forwards `/api` requests to the CapsuleLab API on `http://localhost:8000`.

## Build

```bash
npm run build
```

## Stack

- React
- TypeScript
- Vite
- Tailwind CSS

Keep API proxy changes in `vite.config.ts` aligned with the backend CORS origins in `backend/main.py`.
