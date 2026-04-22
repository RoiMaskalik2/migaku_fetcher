---
name: migaku-fetch
description: Extract Migaku language learning data — known words, book progress, and next reading pages from an EPUB. Trigger when the user provides Migaku credentials and an EPUB file and wants their known words, current reading position, or next pages of text extracted.
---

# Migaku Data Extractor Skill

Extracts three things from a Migaku account in one pass:
1. **Known words** — full WordList dump (dictForm, POS, knownStatus, etc.)
2. **Spider book position** — progressGroupIndex, progressPercentage, comprehension data
3. **Next ~10 pages of text** — ~5,000 Japanese characters starting from current position

All data is consolidated into `migaku_data/summary.md` for easy reading.

## Prerequisites

The following must be provided in the initial prompt before running this skill:
- `EMAIL` — Migaku account email
- `PASSWORD` — Migaku account password
- `EPUB_PATH` — local path to the EPUB file for the book being read
- `BASE_DIR` — absolute path to the project directory (e.g. `C:\Users\mueu2\Desktop\JapaneseBookRecommender`)

## How It Works

### Key Insight
Logging into `study.migaku.com` automatically triggers a network call to
`srs-db-presigned-url-service-api.migaku.com/db-force-sync-download-url`
which returns a signed Google Cloud Storage URL for `{uid}/srs.db.gz` — the
entire SQLite database containing all user data. One Playwright login → one
download → everything.

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
[skip] srs.db already present   # or downloads fresh on first run
[ok] known words: ~7000
[ok] Spider book: 蜘蛛ですが、なにか？...
     progress  : 32.x%
     groupIdx  : 3116
     sentIdx   : ...
[ok] EPUB: <N> lines, starting at 3116
[ok] saved <N> chars → migaku_data/spider_next_10_pages.txt
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
| `migaku_data/summary.md` | Book position, word stats, word list, next pages |
| `migaku_data/known_words.json` | Array of word objects — **see schema below** |
| `migaku_data/spider_book.json` | Full library row for the Spider book |
| `migaku_data/spider_next_10_pages.txt` | Raw ~5,000 char reading text |
| `migaku_data/srs.db` | Cached SQLite DB (delete to force re-download) |

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

**Presigned URL not captured**: Login failed or the network intercept missed the
response. Check credentials. The URL fires within ~10 s of submitting the login
form; the script waits up to 20 s.

**Spider book not found**: The query searches for `蜘蛛`, `spider`, `Spider`, or
`kumo` in the JSON-serialised library row. If the book uses different metadata,
add the relevant keyword to `spider_books` filter in `extract_from_db()`.

**Wrong book selected (WN vs LN)**: The script picks `max(spider_books,
key=lambda b: b.get("progressPercentage") or 0)` — the book with the most
reading progress. If that selects the wrong one, filter by `b['title']`
instead.

**EPUB position off**: `progressGroupIndex` maps to a line number in the
flattened EPUB text. If it overshoots total lines, the script falls back to
`progressPercentage`. Verify with:
```python
import json
d = json.load(open('migaku_data/spider_book.json'))
print(d['progressGroupIndex'], d['progressPercentage'])
```
