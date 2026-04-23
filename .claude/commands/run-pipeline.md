---
name: run-pipeline
description: Pipeline coordinator for the full Japanese vocabulary study flow: Migaku fetch → epub analysis → HTML generation. Use when the user wants to run the whole chain end-to-end or asks what to run next.
---

# Japanese Study Pipeline Coordinator

Runs the three-stage pipeline:
1. **migaku-fetch** — download SRS database, extract known words
2. **epub-word-analysis** — tokenise epub, rank by WaniKani coverage, produce result.json
3. **build_html** — embed data into self-contained index.html

## Prerequisites

Collect from the user before running:
- `BASE_DIR` — e.g. `C:\Users\mueu2\Desktop\JapaneseBookRecommender`
- `EPUB_PATH` — path to the epub file
- `EMAIL` / `PASSWORD` — Migaku account (stored as constants in `migaku_fetch.py`)
- `WK_TOKEN` — WaniKani API token v2 (stored as `WK_TOKEN` constant in `analyze_epub.py`; only needed if changing accounts)

## Full pipeline (2 commands)

```bash
cd <BASE_DIR>

# Stage 1: Migaku → known_words.json  (credentials stored in migaku_fetch.py)
python migaku_fetch.py <EPUB_PATH>

# Stage 2: epub analysis → result.json + index.html  (WK_TOKEN stored in analyze_epub.py)
python analyze_epub.py <EPUB_PATH>
```

`analyze_epub.py` calls `build_html.py` internally, so no third command needed.

## Stage 1 only (known words refresh)

```bash
python migaku_fetch.py <EPUB_PATH>
```

srs.db is cached for 24 hours. Force refresh by deleting it first:
```bash
rm migaku_data/srs.db && python migaku_fetch.py <EPUB_PATH>
```

## Stage 2 only (re-analysis with same known words)

```bash
python analyze_epub.py <EPUB_PATH> <WK_TOKEN>
```

Tokenisation is cached by epub MD5 hash in `data/word_counts_<hash>.json`.
Delete it to force re-tokenisation.

## Stage 3 only (rebuild HTML from existing result.json)

```bash
python build_html.py result.json index.html
```

## Output files

| File | Stage | Contents |
|------|-------|----------|
| `migaku_data/known_words.json` | 1 | Known words (dictForm keys) |
| `migaku_data/summary.md`       | 1 | Book progress + word stats |
| `data/epub_text_<hash>.txt`    | 2 | Cached epub text |
| `data/word_counts_<hash>.json` | 2 | Cached tokenisation |
| `result.json`                  | 2 | Top 100 WK-focused vocab |
| `index.html`                   | 2 | Self-contained study app |

## Configurable parameters (in analyze_epub.py)

| Constant    | Default | Purpose |
|-------------|---------|---------|
| `TOP_N`     | 100     | Max words in output |
| `MIN_FREQ`  | 2       | Minimum occurrence count |
| `N_SECTIONS`| 20      | Epub sections to read |
| `JISHO_LIMIT`| 50     | Words to enrich via Jisho fallback |

## After running

Report to the user:
```
Stage 1: known words: <N>
Stage 2: selected top <N> WK-focused words
         with meanings: <N>
         top 5: <words>
index.html ready — open in browser to study.
```

## Troubleshooting

**`known_words.json` not found**: run stage 1 first.
**WK API 401**: invalid or expired WK token.
**Tokenisation takes long**: normal on first run (~60s for large epub). Cache used afterwards.
**`result.json` has < 100 words**: epub may be short, or WK coverage is low — reduce `MIN_FREQ` or increase `N_SECTIONS`.
