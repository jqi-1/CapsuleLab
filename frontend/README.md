# @capsulelab/frontend

React + TypeScript + Tailwind CSS dashboard for CapsuleLab.

## Setup

```bash
npm install
```

## Development

```bash
npm run dev
```

Starts the Vite dev server on `http://localhost:5173`. Expects the CapsuleLab API at `http://localhost:8000`.

## Build

```bash
npm run build
```

## API Proxy

During development, Vite proxies `/api` requests to `http://localhost:8000`. Configure in `vite.config.ts`.
