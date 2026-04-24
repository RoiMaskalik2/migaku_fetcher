---
name: run-pipeline
description: Pipeline coordinator for the full Japanese vocabulary study flow. Supports two modes: (1) Book pipeline — Migaku fetch → epub analysis → HTML generation; (2) TV show pipeline — SRT subtitle analysis → HTML generation (no Migaku login needed). Use when the user wants to run the whole chain end-to-end or asks what to run next.
---

# Japanese Study Pipeline Coordinator

Two independent pipelines — choose based on the source material:

## Pipeline A: Japanese Book (EPUB)

Runs three stages:
1. **migaku-fetch** — download SRS database, extract known words
2. **epub-word-analysis** — tokenise epub, rank by WaniKani coverage, produce result.json
3. **build_html** — embed data into self-contained index.html

### Prerequisites

Collect from the user before running:
- `BASE_DIR` — e.g. `C:\Users\mueu2\Desktop\JapaneseBookRecommender`
- `EPUB_PATH` — path to the epub file
- `EMAIL` — Migaku account email
- `PASSWORD` — Migaku account password
- `WK_TOKEN` — WaniKani API token (v2)

### Full book pipeline (2 commands)

```bash
cd <BASE_DIR>

# Stage 1: Migaku → known_words.json
python migaku_fetch.py <EPUB_PATH>

# Stage 2: epub analysis → result.json + index.html (all-in-one)
python analyze_epub.py <EPUB_PATH> <WK_TOKEN>
```

`analyze_epub.py` calls `build_html.py` internally, so no third command needed.

### Stage 1 only (known words refresh)

```bash
python migaku_fetch.py <EPUB_PATH>
```

srs.db is cached for 24 hours. Force refresh by deleting it first:
```bash
rm migaku_data/srs.db && python migaku_fetch.py <EPUB_PATH>
```

### Stage 2 only (re-analysis with same known words)

```bash
python analyze_epub.py <EPUB_PATH> <WK_TOKEN>
```

Tokenisation is cached by epub MD5 hash in `data/word_counts_<hash>.json`.
Delete it to force re-tokenisation.

### Output files (book pipeline)

| File | Stage | Contents |
|------|-------|----------|
| `migaku_data/known_words.json` | 1 | Known words (dictForm keys) |
| `migaku_data/summary.md`       | 1 | Book progress + word stats |
| `data/epub_text_<hash>.txt`    | 2 | Cached epub text |
| `data/word_counts_<hash>.json` | 2 | Cached tokenisation |
| `result.json`                  | 2 | Top 100 WK-focused vocab |
| `index.html`                   | 2 | Self-contained study app |

### Configurable parameters (in analyze_epub.py)

| Constant    | Default | Purpose |
|-------------|---------|---------|
| `TOP_N`     | 100     | Max words in output |
| `MIN_FREQ`  | 2       | Minimum occurrence count |
| `N_SECTIONS`| 20      | Epub sections to read |
| `JISHO_LIMIT`| 50     | Words to enrich via Jisho fallback |

---

## Pipeline B: Japanese TV Show / Anime (SRT subtitles)

**No Migaku login required.** Start directly from subtitle files.

Runs two stages:
1. **tv-show-word-analysis** — parse SRT files, tokenise, rank by WaniKani coverage, produce result.json
2. **build_html** — embed data into self-contained index.html (called internally)

### Prerequisites

Collect from the user before running:
- `BASE_DIR` — project directory
- `SRT_PATHS` — one or more `.srt` subtitle files (pass all episodes for a full season)
- `WK_TOKEN` — WaniKani API token (v2)
- `known_words.json` (optional) — if the user has already run `migaku_fetch.py`, it is used automatically for better filtering; otherwise `jp_top1000.txt` alone is used

### Full TV show pipeline (1 command)

```bash
cd <BASE_DIR>

# Single episode
python analyze_srt.py episode01.srt --wk-token <WK_TOKEN>

# Full season (pass all episodes — words are aggregated across all files)
python analyze_srt.py subs/ep01.srt subs/ep02.srt subs/ep03.srt --wk-token <WK_TOKEN>
```

`analyze_srt.py` calls `build_html.py` internally — result.json and index.html are produced in one step.

### Re-analysis with same SRT files

Tokenisation is cached by MD5 hash of the combined subtitle text in `data/srt_counts_<hash>.json`.
Delete it to force re-tokenisation:
```bash
rm data/srt_counts_*.json
python analyze_srt.py <SRT_FILES> --wk-token <WK_TOKEN>
```

### Output files (TV show pipeline)

| File | Contents |
|------|----------|
| `data/srt_counts_<hash>.json` | Cached tokenisation |
| `result.json`                 | Top 100 WK-focused vocab |
| `index.html`                  | Self-contained study app |

### Configurable parameters (in analyze_srt.py)

| Constant  | Default | Purpose |
|-----------|---------|---------|
| `TOP_N`   | 100     | Max words in output |
| `MIN_FREQ`| 2       | Minimum occurrence count |

---

## Stage 3 only (rebuild HTML from existing result.json)

Works for both pipelines:
```bash
python build_html.py result.json index.html
```

---

## After running

Report to the user:

**Book pipeline:**
```
Stage 1: known words: <N>
Stage 2: selected top <N> WK-focused words
         with meanings: <N>
         top 5: <words>
index.html ready — open in browser to study.
```

**TV show pipeline:**
```
SRT files: <N> files parsed
Selected top <N> WK-focused words
  with meanings: <N>
  top 5: <words>
index.html ready — open in browser to study.
```

## Troubleshooting

**`known_words.json` not found (book pipeline)**: run stage 1 first.
**`known_words.json` not found (TV pipeline)**: not an error — `jp_top1000.txt` is used as the sole filter. Run `migaku_fetch.py` first for better filtering.
**WK API 401**: invalid or expired WK token.
**Tokenisation takes long**: normal on first run (~60s for large input). Cache used afterwards.
**`result.json` has < 100 words**: input may be short, or WK coverage is low — reduce `MIN_FREQ` or add more SRT files.
**SRT encoding errors**: files may be Shift-JIS or have a UTF-8 BOM — `analyze_srt.py` handles both automatically.
