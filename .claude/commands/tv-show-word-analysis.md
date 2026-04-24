---
name: tv-show-word-analysis
description: Analyze SRT subtitle files from a Japanese TV show to find the top 100 high-frequency unknown vocabulary with WaniKani kanji mnemonics. Prioritises words whose kanji all appear in WaniKani. Use when the user wants to study vocabulary from a Japanese TV show or anime.
---

# Japanese TV Show Word Frequency Analyzer

Given one or more Japanese `.srt` subtitle files and Migaku known-words data,
produce a ranked JSON list of the **top 100** unknown words (kanji must be in
WaniKani) with frequency, reading, and WaniKani kanji meaning mnemonics.

## Prerequisites

Ask the user for:
- **SRT file paths** — one or more `.srt` files (pass all episodes for full season coverage)
- **WaniKani API token** — required for kanji/vocabulary lookup
- **`BASE_DIR`** — absolute path to the project directory
- **`migaku_data/known_words.json`** — must exist from a prior `migaku-fetch` run

If `known_words.json` is missing, run the `migaku-fetch` skill first.

## Run

```bash
cd <BASE_DIR>

# Single episode
python analyze_srt.py episode01.srt --wk-token <WK_TOKEN>

# Full season
python analyze_srt.py subs/ep01.srt subs/ep02.srt subs/ep03.srt --wk-token <WK_TOKEN>
```

The script handles everything internally: SRT parsing → tokenisation → known-word
filtering → WaniKani ranking → Jisho fallback → `result.json` → `index.html`.

Tokenisation is cached in `data/srt_counts_<hash>.json` — subsequent runs with the
same files skip re-tokenising. If `result.json` already exists, any meanings that
were previously resolved are preserved for words still in the new top-100 list.

## Output

| File | Contents |
|------|----------|
| `data/srt_counts_<hash>.json` | Cached tokenisation |
| `result.json` | Top 100 WK-focused vocab |
| `index.html` | Self-contained study app |

## Report to the user

After the script finishes, report stats only — do NOT echo `result.json`:
```
SRT files: <N> parsed
WK-focused (top 100): <N>  |  With meanings: <N>
Top 5: <word> (<freq>x), ...
index.html ready — open in browser to study.
```

## When meanings are still null after the run

If words remain without meanings after Jisho fallback, look them up manually
(e.g. Jisho web, Takoboto) and patch `result.json` directly, then rebuild:
```bash
python build_html.py result.json index.html
```

## Troubleshooting

**`known_words.json` not found**: run `migaku-fetch` skill first.
**WK API 401**: invalid or expired WaniKani token.
**Tokenisation slow**: normal on first run (~60s). Cache used on subsequent runs.
**< 100 words**: add more SRT files or lower `MIN_FREQ` in `analyze_srt.py`.
**Encoding errors**: the script auto-handles UTF-8, UTF-8-BOM, and Shift-JIS.
