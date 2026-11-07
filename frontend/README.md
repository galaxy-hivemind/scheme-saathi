# Scheme Saathi — Frontend

React + TypeScript frontend for the Scheme Saathi platform.

**This directory is owned by the frontend developer.**

## Setup

```bash
npm install
cp .env.example .env.local   # fill in your values
npm run dev
```

## Environment variables

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | Backend API base URL |

## Connecting to the backend

Set `VITE_API_BASE_URL=http://localhost:8000/api/v1` in `.env.local` to connect to the local backend.

## Development with mocks

Before backend APIs are ready, use the agreed mock response shapes defined in `docs/api-contracts.md`.

Replace mock calls with real API calls once the backend endpoint is verified.
