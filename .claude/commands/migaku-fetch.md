---
name: migaku-fetch
description: Extract Migaku language learning data — known words, book progress, and next reading pages from an EPUB. Trigger when the user provides Migaku credentials and an EPUB file and wants their known words, current reading position, or next pages of text extracted.
---

# Migaku Data Extractor Skill

Extracts three things from a Migaku account in one pass:
1. **Known words** — full WordList dump (dictForm, POS, knownStatus, etc.)
2. **Spider book position** — progressGroupIndex, progressPercentage, comprehension data
3. **Next ~20 pages of text** — ~16,000 Japanese characters starting from current position

All data is consolidated into `migaku_data/summary.md` for easy reading.

## Prerequisites

The following must be provided in the initial prompt before running this skill:
- `EMAIL` — Migaku account email
- `PASSWORD` — Migaku account password
- `EPUB_PATH` — local path to the EPUB file for the book being read
- `BASE_DIR` — absolute path to the project directory (e.g. `C:\Users\mueu2\Desktop\JapaneseBookRecommender`)

## How It Works

### Key Insight — Two separate network calls
Logging into `study.migaku.com` triggers two useful calls:

1. **`srs-db-presigned-url-service-api.migaku.com/db-force-sync-download-url`**
   Returns a **plain-text** GCS URL (not JSON) for `{uid}/srs.db.gz` — the **full**
   SQLite word database (7000+ known words). Parse with `resp.text()`, not `resp.json()`.
   The browser then fetches that GCS URL directly; both are intercepted.

2. **`core-server.migaku.com/pull-sync`**
   Returns `libraryItems` which contains the book reading position
   (`progressGroupIndex`, `progressPercentage`). The `words` array in this
   response is only a small recent batch (~183) — **do NOT use it for filtering**.

The script intercepts both, downloads and reads srs.db via sqlite3, and
combines words + library position into a single cached JSON.

### Book Content
Firebase Storage security rules block all web-authenticated access to book
content files. The user must supply the EPUB file directly (attach in prompt
or provide local path). The script accepts it as `sys.argv[1]`.

## Workflow

Make a todo list for all tasks in this workflow and work on them one by one.

### 1. Update Credentials in migaku_fetch.py

Read `<BASE_DIR>/migaku_fetch.py` and update the constants at the top:

```python
EMAIL    = "<email from prompt>"
PASSWORD = "<password from prompt>"
```

### 2. Ensure the EPUB File is Available

Confirm the EPUB path exists locally. If the user attached a file, note its
path. If not present, ask the user to provide it before continuing.

### 3. Run the Extractor

```bash
cd <BASE_DIR>
python migaku_fetch.py <EPUB_PATH>
```

Expected output:
```
[skip] cached data present   # or fresh login on first run / after cache expiry
[ok] srs.db GCS request URL captured
[ok] srs.db presigned URL captured (plain)
[ok] pull-sync captured (8 libraryItems)
[ok] downloading srs.db.gz...
[ok] srs.db saved (~12000 KB)
[ok] extracted ~7700 words from srs.db
[ok] known words: ~7700
[ok] Spider book: 蜘蛛ですが、なにか？...
     progress  : 33.x%
     groupIdx  : 3262
[ok] EPUB: 5009 non-empty lines, next pages from line ~1652
[ok] saved 16000 chars → migaku_data/spider_next_pages.txt
[ok] summary written → migaku_data/summary.md
```

Note: POS counts in summary.md will show all words as "Other" — Migaku's `WordList`
table stores empty `partOfSpeech` values. This is a Migaku data issue, not a bug.

### 4. Confirm Output and Report Summary Stats Only

Read `migaku_data/summary.md` and report **only the stats section** to the user
(book title, progress %, known word count by POS). Do NOT echo the full word
list — it is too large and the downstream skill reads the file directly.

Report this and nothing more:
```
Book: <title> — <progress>%  (group index: <N>)
Known words: <total> (<KNOWN> known / <SEEN> seen)
  Nouns: N  Verbs: N  Adjectives: N  Other: N
Output saved to migaku_data/
```

### 5. Refresh srs.db (if needed)

If the user wants fresh data (srs.db is cached from a previous run), delete it first:
```bash
rm <BASE_DIR>/migaku_data/srs.db
```
Then re-run step 3.

## Output Files

| File | Contents |
|------|----------|
| `migaku_data/summary.md` | Book position and word stats |
| `migaku_data/known_words.json` | Array of word objects — **see schema below** |
| `migaku_data/spider_book.json` | Full library row for the Spider book |
| `migaku_data/spider_next_pages.txt` | ~16,000 chars (~20 pages) of upcoming reading text |
| `migaku_data/pull_sync.json` | Cached Migaku data (24h TTL) |

## known_words.json Schema

The downstream `epub-word-analysis` skill reads this file. Each item is an object:

```json
[
  {
    "dictForm":    "取得",
    "secondary":   "しゅとく",
    "partOfSpeech": "noun",
    "language":    "ja",
    "knownStatus": 1,
    "hasCard":     true,
    "created":     1710000000
  }
]
```

**Key field for filtering**: `dictForm` — the dictionary base form of the word.
The `epub-word-analysis` skill reads `item['dictForm']`, not `item['word']`.

## Troubleshooting

**SRS URL not captured**: The presigned-URL endpoint returns a **plain-text URL**
(not JSON). If you see `srs URL parse error`, the handler is trying `resp.json()`
instead of `resp.text()` — fix `on_response` in `_fetch_migaku_data`. The URL fires
within ~10 s of login; do NOT navigate away from the page before it arrives or the
in-flight response will be cancelled.

**Known words 0 or very low**: The SQLite word table is named `WordList` (not `Word`).
Check `_read_words_from_db()` — the table search list must include `'WordList'` first.
To confirm the actual table name:
```python
import sqlite3
conn = sqlite3.connect('migaku_data/srs.db')
print([r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")])
```

**Stale cache (pull_sync.json) with wrong word count**: Delete and re-run:
```bash
rm migaku_data/pull_sync.json
python migaku_fetch.py <epub>
```

**Spider book not found**: The query searches for `蜘蛛`, `spider`, `Spider`, or `kumo`
in the JSON-serialised library row. Add the relevant keyword if the title differs.

**EPUB position off**: The script uses `progressPercentage` to locate the reading
position (e.g. 32% → line 1602 of 5009). `progressGroupIndex` reflects Migaku's
internal grouping format which differs from our EPUB line-splitting and is not used.
