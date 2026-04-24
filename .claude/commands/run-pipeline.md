---
name: run-pipeline
description: Pipeline coordinator for the full Japanese vocabulary study flow. Supports two modes: (1) Book pipeline — Migaku fetch → epub analysis → HTML generation; (2) TV show pipeline — Migaku fetch → SRT analysis → HTML generation. Use when the user wants to run the whole chain end-to-end or asks what to run next.
---

# Japanese Study Pipeline Coordinator

Two pipelines — same Stage 1, different Stage 2 depending on source material.

## Prerequisites (both pipelines)

Collect from the user before running:
- `BASE_DIR` — project directory
- `EMAIL` / `PASSWORD` — Migaku account credentials
- `WK_TOKEN` — WaniKani API token (v2)
- Source file(s):
  - **Book**: `EPUB_PATH`
  - **TV show**: one or more `.srt` files

---

## Pipeline A: Japanese Book (EPUB)

```bash
cd <BASE_DIR>

# Stage 1: Migaku → known_words.json
python migaku_fetch.py <EPUB_PATH>

# Stage 2+3: epub → result.json + index.html
python analyze_epub.py <EPUB_PATH> <WK_TOKEN>
```

---

## Pipeline B: Japanese TV Show / Anime (SRT)

```bash
cd <BASE_DIR>

# Stage 1: Migaku → known_words.json (same as book pipeline)
python migaku_fetch.py <EPUB_PATH>

# Stage 2+3: SRT → result.json + index.html
python analyze_srt.py <SRT_FILE> [<SRT_FILE2> ...] --wk-token <WK_TOKEN>
```

Pass all episode SRT files at once — word frequencies are aggregated across all files.

---

## Re-run stages individually

```bash
# Refresh known words (force fresh srs.db download)
rm migaku_data/srs.db && python migaku_fetch.py <EPUB_PATH>

# Re-analyse with same known words (clears tokenisation cache first if needed)
python analyze_epub.py <EPUB_PATH> <WK_TOKEN>          # book
python analyze_srt.py <SRT_FILES> --wk-token <WK_TOKEN>  # TV show

# Rebuild HTML from existing result.json only
python build_html.py result.json index.html
```

---

## Output files

| File | Stage | Contents |
|------|-------|----------|
| `migaku_data/known_words.json` | 1 | Known words (dictForm keys) |
| `migaku_data/summary.md` | 1 | Book progress + word stats |
| `result.json` | 2 | Top 100 WK-focused vocab |
| `index.html` | 2 | Self-contained study app |

---

## After running

Report to the user:
```
Stage 1: known words: <N>
Stage 2: top <N> WK-focused words  |  with meanings: <N>
Top 5: <words>
index.html ready — open in browser to study.
```

## Troubleshooting

**WK API 401**: invalid or expired WaniKani token.
**`known_words.json` not found**: run Stage 1 first.
**`result.json` has < 100 words**: add more source files or lower `MIN_FREQ`.
**Tokenisation slow**: normal on first run; cache used afterwards.
