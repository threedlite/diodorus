# Diodorus: Ancient Text Alignment Pipeline

Adds public domain English translations to ancient Greek and Latin works that
currently exist only in the source language in Perseus and First1KGreek.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run one work
python scripts/pipeline/run.py marcus

# Run all works
python scripts/pipeline/run.py --all

# List available works
python scripts/pipeline/run.py --list
```

## Current Works

| Work | Author | Source | Quality |
|------|--------|--------|:-------:|
| De Compositione Verborum | Dionysius of Halicarnassus | Perseus | 88% high |
| Meditations | Marcus Aurelius | Perseus | 75% high |
| De Mysteriis | Iamblichus | First1KGreek | 73% high |
| Life of Pythagoras | Iamblichus | First1KGreek | 58% high |
| Bibliotheca Historica | Diodorus Siculus | Perseus | 36% high |
| Thebaid + Achilleid | Statius | Perseus | 21% high |
| Fables | Aesop | First1KGreek | 17% high |

## Output

Each work produces three deliverable files in `final/`:

```
<cts_id>.perseus-eng80.xml   — Perseus-compatible TEI translation
<cts_id>.perseus-eng80.svg   — Alignment quality heatmap
<cts_id>.perseus-eng80.html  — Parallel text (source left, English right)
```

## Adding a New Work

Create three files in `scripts/works/<name>/`:
- `config.json` — work metadata and options
- `extract_greek.py` — source text extraction
- `extract_english.py` — English text extraction

Then run: `python scripts/pipeline/run.py <name>`

## Full Documentation

See [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md) for complete details on
architecture, algorithms, data sources, licensing, and how to add new works.

## Prerequisites

- Python 3.11+
- ~5 GB disk for models and data
- Trained embedding model in `models/ancient-greek-embedding/`
  (see `scripts/embedding/` for training pipeline)

## Licensing

All sources are Public Domain / CC0 or CC-BY-SA 4.0. See `LICENSE.txt` for details.
