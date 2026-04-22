#!/usr/bin/env python3
"""
migaku_fetch.py — Extract Migaku known words and book progress via Playwright.

The Migaku app calls core-server.migaku.com/pull-sync on login, which returns
all user data (words, library items) as JSON in one shot.

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

async def _fetch_pull_sync() -> dict:
    from playwright.async_api import async_playwright

    captured = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx  = await browser.new_context()
        page = await ctx.new_page()

        async def on_response(resp):
            if ('core-server.migaku.com/pull-sync' in resp.url
                    and 'serverVersion=0' in resp.url):
                try:
                    data = await resp.json()
                    captured['data'] = data
                    print('[ok] pull-sync data captured')
                except Exception as e:
                    print(f'[warn] pull-sync parse error: {e}')

        page.on('response', on_response)

        print('[auth] navigating to Migaku...')
        try:
            await page.goto('https://study.migaku.com/login',
                            wait_until='domcontentloaded', timeout=60000)
        except Exception as e:
            print(f'[warn] nav: {e}')

        await asyncio.sleep(2)

        try:
            await page.fill('input[type="email"]', EMAIL)
            await page.fill('input[type="password"]', PASSWORD)
            await page.click('button[type="submit"]')
            print('[auth] login submitted')
        except Exception as e:
            print(f'[warn] login form: {e}')

        print('[auth] waiting up to 20s for pull-sync...')
        for _ in range(40):
            await asyncio.sleep(0.5)
            if 'data' in captured:
                break

        await browser.close()

    if 'data' not in captured:
        raise RuntimeError(
            'pull-sync data not captured.\n'
            'Possible causes: wrong credentials, login UI changed, slow network.\n'
            f'Check EMAIL/PASSWORD in {__file__}'
        )

    return captured['data']


def fetch_and_cache() -> dict:
    data = asyncio.run(_fetch_pull_sync())
    CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[ok] data cached -> {CACHE_FILE}')
    return data


def load_data() -> dict:
    if cache_needs_refresh():
        return fetch_and_cache()
    return json.loads(CACHE_FILE.read_text(encoding='utf-8'))


# ── Extraction helpers ─────────────────────────────────────────────────────────

def extract_known_words(data: dict) -> list[dict]:
    raw_words = data.get('words', [])
    words = []
    for w in raw_words:
        if not isinstance(w, dict):
            continue
        if w.get('language') != 'ja':
            continue
        if w.get('del', 0):
            continue

        status_raw = w.get('knownStatus', '')
        # normalise: API sends strings like "KNOWN", "SEEN", "LEARNING"
        if isinstance(status_raw, str):
            known_int = 1 if status_raw == 'KNOWN' else 0
        else:
            known_int = int(status_raw) if status_raw else 0

        words.append({
            'dictForm':     w.get('dictForm', ''),
            'secondary':    w.get('secondary', ''),
            'partOfSpeech': w.get('partOfSpeech', ''),
            'language':     'ja',
            'knownStatus':  known_int,
            'hasCard':      bool(w.get('hasCard', False)),
            'created':      w.get('created', 0),
        })

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

    book  = epub.read_epub(str(epub_path))
    lines = []
    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ITEM_DOCUMENT:
            t = BeautifulSoup(item.get_content(), 'lxml').get_text()
            # Only non-empty lines — Migaku's progressGroupIndex counts sentences, not blank lines
            lines.extend(l for l in t.splitlines() if l.strip())

    total = len(lines)
    start = gidx if gidx < total else max(0, int(total * pct / 100))
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
