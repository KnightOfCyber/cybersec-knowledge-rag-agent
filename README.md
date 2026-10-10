# SOC Investigation Copilot

A read-only copilot that helps an analyst investigate suspicious
authentication activity using linked, source-traceable knowledge in the
[Open Knowledge Format v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format).

Given an alert or question it: retrieves relevant OKF concepts with semantic
search, walks a bounded number of Markdown links, evaluates provenance /
verification / lifecycle / freshness deterministically in Python, drafts an
evidence-grounded investigation plan, and shows sources, trust warnings and
missing evidence. It takes no live security actions.

All bundle guidance is clearly labelled illustrative and for training use.
No real organizational policies are stated, and no unverified content is
marked as human-reviewed (stable notes carry `process:editorial-check`
verification, i.e. machine-confirmed tier).

## Setup (Windows)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
# CPU-only torch first (avoids the large CUDA wheel):
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
copy .env.example .env   # optional, only for the evidence-only LLM summary
streamlit run app.py
```

Large downloads: `torch` (~200 MB CPU wheel) + `sentence-transformers`
dependencies, and the `all-MiniLM-L6-v2` model (~90 MB) on first run.

### Optional local Ollama generation

The app uses deterministic extractive mode by default when Ollama is not
available. To enable local answer generation, install and start Ollama,
then pull a model without changing application startup behavior:

```powershell
ollama pull llama3.2:3b
copy .env.example .env
streamlit run app.py
```

Set `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in `.env` to use another local
Ollama endpoint or installed model. The app checks availability and model
presence at investigation time, never downloads a model automatically, and
labels the active generation mode. Invalid or uncited model output falls
back to deterministic mode with an explicit warning.

## Run tests and evaluation

```powershell
python -m pytest tests/ -v   # fast model-free tests (+ integration if model installed)
python eval.py               # end-to-end retrieval evaluation, needs the model
```

## Project structure

- `okf.py` — deterministic OKF core: concept parsing (unknown types/keys
  preserved), trust tiers from `verified` actors, `status`/`stale_after`
  lifecycle, link resolution + bounded traversal, cosine top-k, plan builder
- `app.py` — semantic retrieval (`all-MiniLM-L6-v2`), investigation
  pipeline, Streamlit GUI (alert input, evidence summary, steps, related
  knowledge, citations, trust/freshness, missing evidence)
- `knowledge/` — OKF bundle: `index.md`, `log.md`, `soc/` (6 core concepts +
  1 deprecated + 1 draft), `cybersecurity/` (5 migrated notes + index)
- `tests/test_soc_copilot.py`, `eval.py` — coverage for multi-document,
  linked, draft, deprecated/stale, no-evidence, conflicting, attribution cases

## Known limitations / next improvement

- Fixed similarity threshold and no reranking; wording-sensitive.
- Next most valuable improvement: log analyst-rated investigations
  (question, cited sources, useful/not) to find weak concepts and tune retrieval.
