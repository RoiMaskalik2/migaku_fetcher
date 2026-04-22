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
   Returns a signed GCS URL for `{uid}/srs.db.gz` — the **full** SQLite word database
   (6000+ known words). This is the authoritative source for all SRS vocabulary.

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
[ok] srs.db presigned URL captured
[ok] pull-sync captured (8 libraryItems)
[ok] downloading srs.db.gz...
[ok] srs.db saved (NNN KB)
[ok] extracted ~6000 words from srs.db
[ok] known words: ~6000
[ok] Spider book: 蜘蛛ですが、なにか？...
     progress  : 32.x%
     groupIdx  : 3116
[ok] EPUB: <N> non-empty lines, next pages from line 3116
[ok] saved <N> chars → migaku_data/spider_next_pages.txt
[ok] summary written → migaku_data/summary.md
```

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

**SRS URL not captured**: Login failed or Migaku changed its API URL. Check credentials.
The presigned-URL call fires within ~10 s of login form submit; script waits up to 30 s.

**Known words low (~183 instead of 6000+)**: The cache (pull_sync.json) was built with
the old pull-sync-only code. Delete it to force a fresh download with the SQLite approach:
```bash
rm migaku_data/pull_sync.json
python migaku_fetch.py <epub>
```

**Word table not found in srs.db**: SQLite schema changed. Run:
```python
import sqlite3
conn = sqlite3.connect('migaku_data/srs.db')
print([r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")])
```
Then update `_read_words_from_db()` with the correct table name.

**Spider book not found**: The query searches for `蜘蛛`, `spider`, `Spider`, or `kumo`
in the JSON-serialised library row. Add the relevant keyword if the title differs.

**EPUB position off**: `progressGroupIndex` counts non-empty EPUB lines. Falls back to
`progressPercentage` if the index exceeds total lines.
