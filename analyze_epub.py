#!/usr/bin/env python3
"""
analyze_epub.py — Produces result.json + index.html from a Japanese epub.

Usage:
    python analyze_epub.py <epub_path> <wanikani_token> [n_sections]

Changes applied:
  - Top 100 words only (freq-ranked, WaniKani-prioritised)
  - WK-focused filtering: words where ALL kanji are in WK first, then SOME
  - WK vocabulary API for word meanings (falls back to Jisho)
  - Scene hook extraction from WK mnemonics
  - Tokenisation cache (word_counts.json) to skip re-tokenising unchanged epubs
"""

import sys, json, time, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from collections import Counter

BASE_DIR    = Path(__file__).parent
MIGAKU_DATA = BASE_DIR / 'migaku_data'
DATA_DIR    = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

WK_TOKEN = "d80065d9-7717-4d27-948c-2ad657faa924"

TOP_N         = 100   # max words in output
MIN_FREQ      = 2     # minimum occurrence count
N_SECTIONS    = 20    # epub sections to read (increase for larger coverage)

KANJI_MIN = ord('一')
KANJI_MAX = ord('鿿')


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_kanji(c: str) -> bool:
    return KANJI_MIN <= ord(c) <= KANJI_MAX


def has_kanji(word: str) -> bool:
    return any(is_kanji(c) for c in word)


def epub_hash(epub_path: Path) -> str:
    h = hashlib.md5(epub_path.read_bytes()).hexdigest()[:8]
    return h


def text_hash(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]


def kata_to_hira(text: str) -> str:
    """Convert katakana to hiragana (U+30A1-U+30F6 → U+3041-U+3096)."""
    return ''.join(
        chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c
        for c in text
    )


# ── Step 1: Extract text from epub ────────────────────────────────────────────

def load_text(epub_path: Path, n_sections: int) -> tuple[str, str]:
    """Return (text, cache_key). Uses spider_next_pages.txt when available."""
    next_pages = MIGAKU_DATA / 'spider_next_pages.txt'
    if next_pages.exists():
        text = next_pages.read_text(encoding='utf-8')
        key  = text_hash(text)
        print(f'[ok] using spider_next_pages.txt ({len(text):,} chars, key={key})')
        return text, key

    cache_key  = epub_hash(epub_path)
    cache_file = DATA_DIR / f'epub_text_{cache_key}.txt'

    if cache_file.exists():
        print(f'[skip] epub text cache found ({cache_file.name})')
        return cache_file.read_text(encoding='utf-8'), cache_key

    from ebooklib import epub, ITEM_DOCUMENT
    from bs4 import BeautifulSoup

    book   = epub.read_epub(str(epub_path))
    texts  = []
    count  = 0

    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ITEM_DOCUMENT:
            t = BeautifulSoup(item.get_content(), 'lxml').get_text()
            if t.strip():
                texts.append(t)
                count += 1
        if count >= n_sections:
            break

    text = '\n'.join(texts)
    cache_file.write_text(text, encoding='utf-8')
    print(f'[ok] epub extracted ({count} sections, {len(text):,} chars)')
    return text, cache_key


# ── Step 2: Tokenise ─────────────────────────────────────────────────────────

def tokenize(text: str, cache_key: str):
    cache_file = DATA_DIR / f'word_counts_{cache_key}.json'

    if cache_file.exists():
        print(f'[skip] tokenisation cache found ({cache_file.name})')
        cached = json.loads(cache_file.read_text(encoding='utf-8'))
        readings = {w: kata_to_hira(r) for w, r in cached['readings'].items()}
        return Counter(cached['counts']), readings

    from janome.tokenizer import Tokenizer
    KEEP_POS = {'名詞', '動詞', '形容詞', '副詞'}
    # Noun sub-types that can start or extend a compound
    NOUN_COMPOUND_TYPES = {'一般', 'サ変接続', '固有名詞', '副詞可能', '数', 'ナイ形容詞語幹'}

    def _keep(base: str) -> bool:
        return (base and base != '*'
                and not all('ぁ' <= c <= 'ゟ' for c in base))

    print('[...] tokenising (first run, may take ~60s)...')
    tokenizer = Tokenizer()
    word_count   = Counter()
    word_reading = {}

    # Buffer for building compound nouns (e.g. 経験 + 値(接尾) → 経験値)
    noun_buf = None   # (base_str, reading_str) | None

    def flush():
        nonlocal noun_buf
        if noun_buf is None:
            return
        base, rdg = noun_buf
        noun_buf = None
        if _keep(base):
            word_count[base] += 1
            if base not in word_reading and rdg:
                word_reading[base] = rdg

    for t in tokenizer.tokenize(text):
        pos_parts  = t.part_of_speech.split(',')
        pos        = pos_parts[0]
        pos_detail = pos_parts[1] if len(pos_parts) > 1 else '*'
        base    = t.base_form if (t.base_form and t.base_form != '*') else t.surface
        reading = kata_to_hira(t.reading) if (t.reading and t.reading != '*') else ''

        if not base:
            flush()
            continue

        if pos == '名詞':
            if pos_detail == '接尾' and noun_buf is not None:
                # Extend the buffered compound with this suffix (e.g. 値 in 経験値)
                noun_buf = (noun_buf[0] + base, noun_buf[1] + reading)
            elif pos_detail in NOUN_COMPOUND_TYPES:
                flush()
                noun_buf = (base, reading)
            else:
                flush()
        elif pos in KEEP_POS:
            flush()
            if _keep(base):
                word_count[base] += 1
                if base not in word_reading and reading:
                    word_reading[base] = reading
        else:
            flush()

    flush()  # end of stream

    cache_file.write_text(
        json.dumps({'counts': dict(word_count), 'readings': word_reading}, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f'[ok] tokenised: {len(word_count)} unique words')
    return word_count, word_reading


# ── Step 3: Filter against known words ───────────────────────────────────────

def filter_known(word_count: Counter, word_reading: dict) -> list[tuple[str, int]]:
    known_file = MIGAKU_DATA / 'known_words.json'
    top1k_file = DATA_DIR / 'jp_top1000.txt'

    known = set()
    if known_file.exists():
        raw = json.loads(known_file.read_text(encoding='utf-8'))
        for item in raw:
            if isinstance(item, dict):
                known.add(item.get('dictForm', ''))
            else:
                known.add(item)
        known.discard('')
        print(f'[ok] loaded {len(known)} known words from Migaku')
    else:
        print('[warn] known_words.json not found — run migaku_fetch.py first')

    # jp_top1000.txt covers basic vocabulary the user knows but hasn't tracked in Migaku SRS
    common = set()
    if top1k_file.exists():
        common = {l.strip() for l in top1k_file.read_text(encoding='utf-8').splitlines() if l.strip()}
        print(f'[ok] loaded {len(common)} common words from jp_top1000.txt')

    candidates = [
        (w, cnt) for w, cnt in word_count.most_common()
        if w not in known and w not in common and cnt >= MIN_FREQ and has_kanji(w)
    ]
    print(f'[ok] {len(candidates)} unknown kanji-words with freq >= {MIN_FREQ}')
    return candidates


# ── Step 4: Fetch WaniKani data — kanji + vocabulary ─────────────────────────

WK_KANJI_CACHE = DATA_DIR / 'wk_kanji_cache.json'


def _load_wk_kanji_cache() -> dict:
    if WK_KANJI_CACHE.exists():
        return json.loads(WK_KANJI_CACHE.read_text(encoding='utf-8'))
    return {}


def _save_wk_kanji_cache(wk_kanji: dict) -> None:
    cache = _load_wk_kanji_cache()
    cache.update(wk_kanji)
    WK_KANJI_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')


def fetch_wanikani(candidates: list[tuple[str, int]], wk_token: str):
    import requests

    headers = {'Authorization': f'Bearer {wk_token}'}

    # Collect all unique kanji across ALL candidates (not just top 100 yet)
    all_kanji = sorted({c for w, _ in candidates for c in w if is_kanji(c)})
    if not all_kanji:
        return {}

    # Serve already-cached kanji without a network call
    disk_cache = _load_wk_kanji_cache()
    wk_kanji   = {k: v for k, v in disk_cache.items() if k in set(all_kanji)}
    missing    = [k for k in all_kanji if k not in wk_kanji]

    if missing:
        print(f'[wk] fetching {len(missing)} kanji subjects ({len(wk_kanji)} from cache)...')
        batch_size = 100  # stay well under URL length limits
        for i in range(0, len(missing), batch_size):
            batch = missing[i:i + batch_size]
            for attempt in range(4):
                resp = requests.get(
                    'https://api.wanikani.com/v2/subjects',
                    params={'types': 'kanji', 'slugs': ','.join(batch)},
                    headers=headers,
                    timeout=30
                )
                if resp.status_code == 503:
                    wait = 2 ** attempt
                    print(f'[wk] 503, retrying in {wait}s...')
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                for s in resp.json()['data']:
                    wk_kanji[s['data']['characters']] = s['data']
                time.sleep(0.3)
                break
        _save_wk_kanji_cache(wk_kanji)
    else:
        print(f'[wk] all {len(all_kanji)} kanji served from cache')

    print(f'[wk] got {len(wk_kanji)}/{len(all_kanji)} kanji in WaniKani')
    return wk_kanji


def fetch_wk_vocab(words: list[str], wk_token: str) -> dict:
    import requests
    if not words:
        return {}

    headers = {'Authorization': f'Bearer {wk_token}'}
    slugs   = ','.join(words[:200])  # WK API limit

    print(f'[wk] fetching vocabulary meanings for up to {len(words)} words...')
    for attempt in range(4):
        resp = requests.get(
            'https://api.wanikani.com/v2/subjects',
            params={'types': 'vocabulary', 'slugs': slugs},
            headers=headers,
            timeout=30
        )
        if resp.status_code == 503:
            wait = 2 ** attempt
            print(f'[wk] vocab 503, retrying in {wait}s...')
            time.sleep(wait)
            continue
        break
    resp.raise_for_status()
    wk_vocab = {s['data']['characters']: s['data'] for s in resp.json()['data']}
    print(f'[wk] got vocab meanings for {len(wk_vocab)}/{len(words)} words')
    return wk_vocab


# ── Step 5: WaniKani-focused ranking ──────────────────────────────────────────

def rank_by_wanikani(candidates: list[tuple[str, int]], wk_kanji: dict) -> list[tuple[str, int]]:
    """Sort candidates: all-WK-kanji first, then some-WK-kanji, sorted by freq within tier."""
    tier1, tier2 = [], []
    for w, cnt in candidates:
        chars = [c for c in w if is_kanji(c)]
        if not chars:
            continue
        in_wk = sum(1 for c in chars if c in wk_kanji)
        if in_wk == len(chars):
            tier1.append((w, cnt))
        elif in_wk > 0:
            tier2.append((w, cnt))
        # Words with zero WK kanji are dropped

    print(f'[wk] tier1 (all kanji in WK): {len(tier1)}, tier2 (partial): {len(tier2)}')
    result = tier1 + tier2  # both already sorted by freq from most_common()
    return result[:TOP_N]


# ── Step 6: Build result entries ──────────────────────────────────────────────

def build_result(words: list[tuple[str, int]], wk_kanji: dict, wk_vocab: dict,
                 word_reading: dict) -> list[dict]:
    result = []
    for word, freq in words:
        # Word-level meaning from WK vocab
        wv  = wk_vocab.get(word, {})
        meaning = None
        if wv:
            wv_meanings = wv.get('meanings', [])
            meaning = next((m['meaning'] for m in wv_meanings if m.get('primary')), None)

        # Kanji entries
        kanji_list = []
        for c in word:
            if not is_kanji(c):
                continue
            d = wk_kanji.get(c, {})
            meanings  = d.get('meanings', [])
            readings  = d.get('readings', [])
            pm = next((m['meaning'] for m in meanings if m.get('primary')), None)
            pr = next((r['reading'] for r in readings if r.get('primary')), None)
            kanji_list.append({
                'character':        c,
                'meaning':          pm,
                'reading':          pr,
                'meaning_mnemonic': d.get('meaning_mnemonic'),
            })

        result.append({
            'word':                 word,
            'reading':              word_reading.get(word, ''),
            'meaning':              meaning,
            'frequency_in_section': freq,
            'kanji':                kanji_list,
        })
    return result


# ── Step 7: Jisho fallback for missing meanings ───────────────────────────────

def enrich_jisho(result: list[dict]) -> list[dict]:
    import requests

    missing = [e for e in result if e['meaning'] is None]
    if not missing:
        return result

    print(f'[jisho] enriching {len(missing)} words without WK meanings...')
    for entry in missing:
        try:
            r = requests.get(
                'https://jisho.org/api/v1/search/words',
                params={'keyword': entry['word']},
                timeout=10
            )
            data = r.json().get('data', [])
            if data and data[0].get('senses'):
                entry['meaning'] = data[0]['senses'][0]['english_definitions'][0]
        except Exception:
            pass
        time.sleep(0.25)

    enriched = sum(1 for e in missing if e['meaning'] is not None)
    print(f'[jisho] enriched {enriched}/{len(missing)} words')

    still_missing = [e['word'] for e in missing if e['meaning'] is None]
    if still_missing:
        print(f'[warn] {len(still_missing)} words still have no meaning: {still_missing}')

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print('Usage: python analyze_epub.py <epub_path> [wanikani_token] [n_sections]')
        sys.exit(1)

    epub_path = Path(sys.argv[1])
    wk_token  = sys.argv[2] if len(sys.argv) > 2 else WK_TOKEN
    n_sec     = int(sys.argv[3]) if len(sys.argv) > 3 else N_SECTIONS

    if not epub_path.exists():
        print(f'[error] epub not found: {epub_path}')
        sys.exit(1)

    # 1. Extract text
    text, cache_key = load_text(epub_path, n_sec)

    # 2. Tokenise
    word_count, word_reading = tokenize(text, cache_key)

    # 3. Filter
    candidates = filter_known(word_count, word_reading)

    # 4. Fetch WaniKani kanji data for all candidates
    wk_kanji = fetch_wanikani(candidates, wk_token)

    # 5. Rank by WaniKani coverage, take top 100
    final_words = rank_by_wanikani(candidates, wk_kanji)
    print(f'[ok] selected top {len(final_words)} WK-focused words')

    # 6. Fetch WK vocab meanings
    wk_vocab = fetch_wk_vocab([w for w, _ in final_words], wk_token)

    # 7. Build result
    result = build_result(final_words, wk_kanji, wk_vocab, word_reading)

    # 8. Jisho fallback
    result = enrich_jisho(result)

    # 9. Save result.json
    out = BASE_DIR / 'result.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[ok] result.json written ({len(result)} words)')

    # 10. Generate index.html
    from build_html import build_html
    build_html(result, BASE_DIR / 'index.html')

    # Stats
    print('\n── Stats ──────────────────────────────')
    print(f'Words analysed (epub):     {sum(word_count.values()):,}')
    print(f'Unknown kanji-words:       {len(candidates)}')
    print(f'WK-focused (top {TOP_N}):       {len(result)}')
    print(f'With meanings:             {sum(1 for e in result if e["meaning"])}')
    top5 = result[:5]
    top5_str = ', '.join(f'{e["word"]} ({e["frequency_in_section"]}x)' for e in top5)
    print(f'Top 5: {top5_str}')
    print(f'index.html written to {BASE_DIR / "index.html"}')


if __name__ == '__main__':
    main()
