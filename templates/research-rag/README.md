# Research RAG Project

RAG retrieval-augmented generation research project with notebooks, evaluation, and source tracking.

## Quick Start

```bash
cap doctor
cap build
cap start
cap app start jupyter
cap app open jupyter
```

## Apps

- **JupyterLab** — notebooks for exploration, retrieval testing, and evaluation

## Project Structure

```
notebooks/       — exploration and evaluation notebooks
src/             — reusable source code
data/            — datasets (gitignored)
models/          — model cache (gitignored)
experiments/     — experiment tracking and notes
outputs/         — generated outputs and reports
papers/          — source notes for papers and documents
graph/           — graph-ready context notes
reports/         — reproducibility reports
```

## Retrieval And Evaluation

- Put shareable text fixtures in `data/`.
- Record paper and source provenance in `papers/sources.md`.
- Use `src/retrieval.py` for a simple keyword-search baseline.
- Record metrics in `experiments/evaluation_runs.md`.
- Keep project-level reproducibility notes in `reports/reproducibility.md`.
