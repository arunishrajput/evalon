# EVALON — Hackathon Evaluation Engine

Full spec: `docs/SPEC.md`.

## What this is

Participants submit a GitHub repo URL. The system clones it, runs static analysis,
runs 3 sequential AI agents, and produces an explainable, evidence-backed scorecard.

## Non-negotiable principles

1. Tools measure. AI explains. Scores come from structured tool output, never a raw LLM number.
2. Every score traces to specific observed evidence. "Good code quality" is a bug.
3. One agent failure never crashes the pipeline. Degrade, don't fail.
4. Never execute cloned code. Static analysis only.
5. Never load two Ollama models at once. All inference is serialized.
6. Agents run SEQUENTIALLY. Never in parallel.
7. No raw error or 500 ever reaches the UI. Every failure has a human-readable state.

## Stack

Backend: Python 3.11, FastAPI async, SQLAlchemy 2.0 async, Alembic, Pydantic v2, ARQ
AI: LangGraph, Ollama (qwen2.5-coder:7b + nomic-embed-text)
Data: PostgreSQL 16 + pgvector, Redis 7
Frontend: Next.js 14 App Router, Tailwind, shadcn/ui, Recharts, Zustand, SWR

## Commands

make dev # postgres + redis in docker; backend + frontend native with hot reload
make migrate # alembic upgrade head
make seed # admin + 3 participants + demo hackathon
make test

## Working rules

- Plan before anything structural.
