#!/usr/bin/env python3
"""
migaku_fetch.py — Extract Migaku known words and book progress via Playwright.

On login, Migaku fires two useful network calls:
  1. srs-db-presigned-url-service-api → signed GCS URL for srs.db.gz (full SQLite word DB)
  2. core-server.migaku.com/pull-sync → libraryItems for book reading position

The pull-sync JSON only contains recently-synced words (~183); the SQLite database
contains the full SRS vocabulary (6000+). We intercept both.

Usage:
    python migaku_fetch.py <epub_path>
"""

import sys, json, asyncio, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

BASE_DIR    = Path(__file__).parent
MIGAKU_DATA = BASE_DIR / 'migaku_data'
MIGAKU_DATA.mkdir(exist_ok=True)

EMAIL    = "roi.maskalik@gmail.com"
PASSWORD = "0r5r4r"

CACHE_FILE     = MIGAKU_DATA / 'pull_sync.json'
CACHE_MAX_AGE_H = 24  # hours before forcing a re-download


# ── Cache helpers ─────────────────────────────────────────────────────────────

def cache_needs_refresh() -> bool:
    if not CACHE_FILE.exists():
        return True
    age_h = (time.time() - CACHE_FILE.stat().st_mtime) / 3600
    if age_h > CACHE_MAX_AGE_H:
        print(f'[info] cache is {age_h:.1f}h old (>{CACHE_MAX_AGE_H}h) — refreshing')
        return True
    print(f'[skip] cached data present ({age_h:.1f}h old)')
    return False


# ── Playwright download ────────────────────────────────────────────────────────

async def _fetch_migaku_data() -> dict:
    """
    Intercept two Migaku network calls:
      1. srs-db-presigned-url-service-api  → signed URL for the full srs.db.gz
      2. core-server.migaku.com/pull-sync  → libraryItems for book position

    The pull-sync JSON only returns a small batch of recently-synced words.
    The full SRS word database (6000+ words) lives in srs.db.gz.
    """
    from playwright.async_api import async_playwright
    import gzip, sqlite3, tempfile, urllib.request

    captured = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx  = await browser.new_context(ignore_https_errors=True)
        page = await ctx.new_page()

        async def on_response(resp):
            # Presigned URL for the full SQLite word database
            if 'srs-db-presigned-url-service-api' in resp.url and 'db-force-sync-download-url' in resp.url:
                try:
                    text = await resp.text()
                    if not text.strip():
                        print(f'[warn] srs URL response empty, status={resp.status}')
                    elif text.strip().startswith('{'):
                        data = json.loads(text)
                        captured['srs_url'] = (data.get('url') or data.get('downloadUrl')
                                               or data.get('signedUrl') or data.get('presignedUrl'))
                        print(f'[ok] srs.db presigned URL captured (JSON)')
                    else:
                        # Plain-string URL
                        url = text.strip().strip('"')
                        if url.startswith('http'):
                            captured['srs_url'] = url
                            print(f'[ok] srs.db presigned URL captured (plain)')
                        else:
                            print(f'[warn] unexpected srs URL body: {text[:120]}')
                except Exception as e:
                    print(f'[warn] srs URL parse error: {e}')

            # Catch the actual GCS download when the browser fetches srs.db.gz directly
            if 'srs_url' not in captured and 'storage.googleapis.com' in resp.url and 'srs' in resp.url.lower():
                captured['srs_url'] = resp.url
                print(f'[ok] srs.db GCS URL captured directly')

            # pull-sync for libraryItems (book position) — accept any serverVersion
            if 'core-server.migaku.com/pull-sync' in resp.url:
                try:
                    data = await resp.json()
                    # Keep the response with the most libraryItems
                    lib = data.get('libraryItems', [])
                    if lib and len(lib) > len(captured.get('library_items', [])):
                        captured['library_items'] = lib
                        print(f'[ok] pull-sync captured ({len(lib)} libraryItems)')
                except Exception as e:
                    print(f'[warn] pull-sync parse error: {e}')

        # Intercept direct GCS requests for .db.gz (handles 302 redirect from presigned-URL service)
        async def on_request(req):
            if 'srs_url' not in captured and 'storage.googleapis.com' in req.url and '.db' in req.url:
                captured['srs_url'] = req.url
                print(f'[ok] srs.db GCS request URL captured')

        page.on('response', on_response)
        page.on('request', on_request)

        print('[auth] navigating to Migaku...')
        try:
            await page.goto('https://study.migaku.com/login',
                            wait_until='domcontentloaded', timeout=60000)
        except Exception as e:
            print(f'[warn] nav: {e}')

        try:
            await page.wait_for_selector('input[type="email"]', timeout=30000)
            await page.fill('input[type="email"]', EMAIL)
            await page.fill('input[type="password"]', PASSWORD)
            await page.click('button[type="submit"]')
            print('[auth] login submitted')
        except Exception as e:
            print(f'[warn] login form: {e}')

        # Wait for both signals — the SRS URL fires automatically after login
        print('[auth] waiting up to 60s for SRS database URL...')
        for _ in range(120):
            await asyncio.sleep(0.5)
            if 'srs_url' in captured and 'library_items' in captured:
                break

        # If we got the SRS URL but still no library items, navigate to the
        # library page to trigger a fresh pull-sync request
        if 'srs_url' in captured and 'library_items' not in captured:
            print('[auth] navigating to library page to trigger pull-sync...')
            try:
                await page.goto('https://study.migaku.com/library',
                                wait_until='domcontentloaded', timeout=30000)
            except Exception as e:
                print(f'[warn] library nav: {e}')
            for _ in range(60):
                await asyncio.sleep(0.5)
                if 'library_items' in captured:
                    break
            if 'library_items' not in captured:
                print('[warn] library_items still not captured after library nav')

        await browser.close()

    if 'srs_url' not in captured:
        raise RuntimeError(
            'SRS database URL not captured. Login may have failed or Migaku changed its API.\n'
            f'Check EMAIL/PASSWORD in {__file__}'
        )

    # Download and read the SQLite database
    srs_url = captured['srs_url']
    print(f'[ok] downloading srs.db.gz...')
    db_path = MIGAKU_DATA / 'srs.db'

    with tempfile.NamedTemporaryFile(suffix='.db.gz', delete=False) as tmp:
        tmp_gz = tmp.name

    urllib.request.urlretrieve(srs_url, tmp_gz)
    with gzip.open(tmp_gz, 'rb') as f_in:
        db_path.write_bytes(f_in.read())
    print(f'[ok] srs.db saved ({db_path.stat().st_size // 1024} KB)')

    # Extract words from SQLite
    words = _read_words_from_db(db_path)
    print(f'[ok] extracted {len(words)} words from srs.db')

    # pull-sync only returns delta updates; fall back to the library table in srs.db
    library_items = captured.get('library_items', [])
    if not library_items:
        library_items = _read_library_from_db(db_path)
        if library_items:
            print(f'[ok] library loaded from srs.db ({len(library_items)} items)')

    return {
        'words':        words,
        'libraryItems': library_items,
    }


def _read_words_from_db(db_path) -> list[dict]:
    """Read Japanese words from Migaku's SQLite database."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Discover the word table name
    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    word_table = next((t for t in ['WordList', 'Word', 'word', 'Words', 'words', 'Vocab', 'vocab'] if t in tables), None)

    if not word_table:
        print(f'[warn] known tables: {tables}')
        conn.close()
        return []

    rows = cur.execute(f'SELECT * FROM {word_table}').fetchall()
    conn.close()

    words = []
    for row in rows:
        d = dict(row)
        # Handle both camelCase and snake_case column names
        dict_form = d.get('dictForm') or d.get('dict_form', '')
        lang      = d.get('language') or d.get('lang', '')
        deleted   = d.get('del') or d.get('deleted', 0)
        status    = d.get('knownStatus') or d.get('known_status', '')

        if lang != 'ja' or deleted:
            continue

        if isinstance(status, str):
            known_int = 1 if status == 'KNOWN' else 0
        else:
            known_int = int(status) if status else 0

        words.append({
            'dictForm':     dict_form,
            'secondary':    d.get('secondary', ''),
            'partOfSpeech': d.get('partOfSpeech') or d.get('part_of_speech', ''),
            'language':     'ja',
            'knownStatus':  known_int,
            'hasCard':      bool(d.get('hasCard') or d.get('has_card', False)),
            'created':      d.get('created', 0),
        })
    return words


def _read_library_from_db(db_path) -> list[dict]:
    """Read library items (books + progress) from Migaku's SQLite database."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if 'library' not in tables:
        conn.close()
        return []

    rows = cur.execute('SELECT * FROM library').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_and_cache() -> dict:
    data = asyncio.run(_fetch_migaku_data())
    CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[ok] data cached -> {CACHE_FILE}')
    return data


def load_data() -> dict:
    if cache_needs_refresh():
        return fetch_and_cache()
    return json.loads(CACHE_FILE.read_text(encoding='utf-8'))


# ── Extraction helpers ─────────────────────────────────────────────────────────

def extract_known_words(data: dict) -> list[dict]:
    # Words are already normalized by _read_words_from_db
    words = [w for w in data.get('words', []) if isinstance(w, dict)]
    (MIGAKU_DATA / 'known_words.json').write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f'[ok] known words: {len(words)}')
    return words


def find_spider_book(data: dict) -> dict | None:
    lib = data.get('libraryItems', [])
    candidates = []
    for item in lib:
        if not isinstance(item, dict): continue
        if item.get('del', 0): continue
        row_str = json.dumps(item, ensure_ascii=False)
        if any(kw in row_str for kw in ['蜘蛛', 'spider', 'Spider', 'kumo', 'Kumo']):
            candidates.append(item)

    if not candidates:
        return None

    # Prefer the one with most reading progress
    best = max(candidates, key=lambda b: b.get('progressPercentage') or 0)
    (MIGAKU_DATA / 'spider_book.json').write_text(
        json.dumps(best, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    title = best.get('title', '?')
    pct   = best.get('progressPercentage', 0) or 0
    gidx  = best.get('progressGroupIndex')  or 0
    print(f'[ok] Spider book: {title}')
    print(f'     progress  : {pct:.1f}%')
    print(f'     groupIdx  : {gidx}')
    return best


def extract_epub_text(epub_path: Path, spider_book: dict | None) -> None:
    from ebooklib import epub, ITEM_DOCUMENT
    from bs4 import BeautifulSoup

    gidx = 0
    pct  = 0.0
    if spider_book:
        gidx = int(spider_book.get('progressGroupIndex') or 0)
        pct  = float(spider_book.get('progressPercentage') or 0)

    from bs4 import XMLParsedAsHTMLWarning
    import warnings
    warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)

    book  = epub.read_epub(str(epub_path))
    lines = []
    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ITEM_DOCUMENT:
            t = BeautifulSoup(item.get_content(), 'lxml').get_text()
            # Only non-empty lines — Migaku's progressGroupIndex counts sentences, not blank lines
            lines.extend(l for l in t.splitlines() if l.strip())

    total = len(lines)
    # progressGroupIndex uses Migaku's internal grouping which differs from our
    # EPUB line-splitting; progressPercentage is always accurate
    start = max(0, int(total * pct / 100)) if pct > 0 else gidx
    chunk = '\n'.join(lines[start:start + 1000])[:16000]  # ~20 pages

    out = MIGAKU_DATA / 'spider_next_pages.txt'
    out.write_text(chunk, encoding='utf-8')
    print(f'[ok] EPUB: {total} non-empty lines, next pages from line {start}')
    print(f'[ok] saved {len(chunk)} chars → migaku_data/spider_next_pages.txt')


def write_summary(words: list[dict], spider_book: dict | None) -> None:
    from collections import Counter
    pos_c       = Counter(w.get('partOfSpeech', 'other') for w in words)
    known_count = sum(1 for w in words if w.get('knownStatus', 0) >= 1)
    seen_count  = sum(1 for w in words if w.get('knownStatus', 0) == 0 and w.get('hasCard'))

    title = '?'
    pct   = 0.0
    gidx  = 0
    if spider_book:
        title = spider_book.get('title', '?')
        pct   = float(spider_book.get('progressPercentage') or 0)
        gidx  = int(spider_book.get('progressGroupIndex') or 0)

    noun_c  = pos_c.get('noun', 0)
    verb_c  = pos_c.get('verb', 0)
    adj_c   = pos_c.get('adjective', 0) + pos_c.get('i-adjective', 0)
    other_c = len(words) - noun_c - verb_c - adj_c

    lines = [
        '# Migaku Summary',
        '',
        f'Book: {title} — {pct:.1f}%  (group index: {gidx})',
        f'Known words: {len(words)} ({known_count} known / {seen_count} seen)',
        f'  Nouns: {noun_c}',
        f'  Verbs: {verb_c}',
        f'  Adjectives: {adj_c}',
        f'  Other: {other_c}',
    ]
    (MIGAKU_DATA / 'summary.md').write_text('\n'.join(lines), encoding='utf-8')
    print('[ok] summary written → migaku_data/summary.md')
    for line in lines[2:]:
        print(line)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print('Usage: python migaku_fetch.py <epub_path>')
        sys.exit(1)

    epub_path = Path(sys.argv[1])
    if not epub_path.exists():
        print(f'[error] EPUB not found: {epub_path}')
        sys.exit(1)

    data        = load_data()
    words       = extract_known_words(data)
    spider_book = find_spider_book(data)
    extract_epub_text(epub_path, spider_book)
    write_summary(words, spider_book)


if __name__ == '__main__':
    main()
