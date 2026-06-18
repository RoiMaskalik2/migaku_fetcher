#!/usr/bin/env python3
"""
analyze_epub.py — Produces result.json + index.html from a Japanese epub.

Usage:
    python analyze_epub.py <epub_path> <wanikani_token> [n_sections]

Changes applied:
  - Top 100 words only, ranked purely by frequency (kanji and kana-only
    words compete equally — WaniKani coverage no longer gates selection,
    it just decides which kanji mnemonics get shown)
  - WK vocabulary API for word meanings (falls back to Jisho)
  - Scene hook extraction from WK mnemonics
  - Reads the entire epub by default (pass n_sections to cap it)
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
N_SECTIONS    = None  # epub sections to read; None = entire book

KANJI_MIN = ord('一')
KANJI_MAX = ord('鿿')


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_kanji(c: str) -> bool:
    return KANJI_MIN <= ord(c) <= KANJI_MAX


def epub_hash(epub_path: Path) -> str:
    h = hashlib.md5(epub_path.read_bytes()).hexdigest()[:8]
    return h


def cache_key_for(epub_path: Path, n_sections) -> str:
    """Cache key incorporating section scope, so a full-book run never reuses
    a cache built from a narrower (e.g. first-20-sections) run."""
    scope = 'all' if n_sections is None else str(n_sections)
    return f'{epub_hash(epub_path)}_{scope}'


def kata_to_hira(text: str) -> str:
    """Convert katakana to hiragana (U+30A1-U+30F6 → U+3041-U+3096)."""
    return ''.join(
        chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c
        for c in text
    )


# ── Step 1: Extract text from epub ────────────────────────────────────────────

def load_text(epub_path: Path, n_sections, cache_key: str) -> str:
    cache_file = DATA_DIR / f'epub_text_{cache_key}.txt'

    if cache_file.exists():
        print(f'[skip] epub text cache found ({cache_file.name})')
        return cache_file.read_text(encoding='utf-8')

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
        if n_sections is not None and count >= n_sections:
            break

    text = '\n'.join(texts)
    cache_file.write_text(text, encoding='utf-8')
    print(f'[ok] epub extracted ({count} sections, {len(text):,} chars)')
    return text


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

    def _is_japanese(s: str) -> bool:
        for c in s:
            if is_kanji(c):
                continue
            if 'ぁ' <= c <= 'ゟ':  # hiragana incl. extensions
                continue
            if '゠' <= c <= 'ヿ':  # katakana incl. extensions
                continue
            if c in 'ーゝゞ・':
                continue
            return False
        return True

    def _keep(base: str) -> bool:
        # Pure-hiragana/katakana words are kept too — they're filtered out
        # later by frequency/known-word checks, not blanket-excluded here.
        # Full-width Latin/digits/punctuation that janome mistags as nouns
        # are rejected here since they aren't real vocabulary.
        return base and base != '*' and len(base) >= 2 and _is_japanese(base)

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
        if w not in known and w not in common and cnt >= MIN_FREQ
    ]
    print(f'[ok] {len(candidates)} unknown words with freq >= {MIN_FREQ}')
    return candidates


# ── Step 4: Fetch WaniKani data — kanji + vocabulary ─────────────────────────

def fetch_wanikani(candidates: list[tuple[str, int]], wk_token: str):
    import requests

    headers = {'Authorization': f'Bearer {wk_token}'}

    # Collect all unique kanji across the given candidates
    all_kanji = sorted({c for w, _ in candidates for c in w if is_kanji(c)})
    if not all_kanji:
        return {}, {}

    print(f'[wk] fetching {len(all_kanji)} kanji subjects...')
    wk_kanji = {}
    batch_size = 100  # stay well under URL length limits
    for i in range(0, len(all_kanji), batch_size):
        batch = all_kanji[i:i + batch_size]
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
    print(f'[wk] got {len(wk_kanji)}/{len(all_kanji)} kanji in WaniKani')

    return wk_kanji


def load_kanji_cache() -> dict:
    """Build a kanji dict from any existing result*.json files."""
    cache = {}
    for f in BASE_DIR.glob('result*.json'):
        try:
            for entry in json.loads(f.read_text(encoding='utf-8')):
                for k in entry.get('kanji', []):
                    c = k.get('character')
                    if c and c not in cache:
                        cache[c] = {
                            'meanings':          [{'meaning': k['meaning'], 'primary': True}] if k.get('meaning') else [],
                            'readings':          [{'reading': k['reading'], 'primary': True}] if k.get('reading') else [],
                            'meaning_mnemonic':  k.get('meaning_mnemonic'),
                        }
        except Exception:
            pass
    if cache:
        print(f'[cache] loaded {len(cache)} kanji from existing result files')
    return cache


def fetch_wanikani_with_fallback(candidates: list[tuple[str, int]], wk_token: str) -> dict:
    """Try WK API; on failure (e.g. hibernating account) return local cache only."""
    local = load_kanji_cache()
    try:
        wk = fetch_wanikani(candidates, wk_token)
        # Merge: prefer fresh WK data, fill gaps from local cache
        return {**local, **wk}
    except Exception as e:
        print(f'[warn] WK API unavailable ({e}) — using local kanji cache only')
        return local


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


# ── Step 5: Select top words by frequency ────────────────────────────────────

def select_top_words(candidates: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Take the top TOP_N candidates by raw frequency — already sorted via
    most_common(). Kanji and kana-only words compete equally; WaniKani
    coverage doesn't gate selection, it only decides what mnemonics show up
    for whichever kanji happen to be WK subjects."""
    selected  = candidates[:TOP_N]
    kana_only = sum(1 for w, _ in selected if not any(is_kanji(c) for c in w))
    print(f'[ok] top {len(selected)} by frequency '
          f'({len(selected) - kana_only} with kanji, {kana_only} kana-only)')
    return selected


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
    cache_key = cache_key_for(epub_path, n_sec)
    text = load_text(epub_path, n_sec, cache_key)

    # 2. Tokenise
    word_count, word_reading = tokenize(text, cache_key)

    # 3. Filter
    candidates = filter_known(word_count, word_reading)

    # 4. Select top 100 by raw frequency (kanji + kana mixed)
    final_words = select_top_words(candidates)

    # 5. Fetch WaniKani kanji data for the selected words' kanji (falls back to
    #    local result*.json cache if the WK account is hibernating / API fails)
    wk_kanji = fetch_wanikani_with_fallback(final_words, wk_token)

    # 6. Fetch WK vocab meanings
    try:
        wk_vocab = fetch_wk_vocab([w for w, _ in final_words], wk_token)
    except Exception as e:
        print(f'[warn] WK vocab unavailable ({e}) — meanings from Jisho only')
        wk_vocab = {}

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
    print(f'Unknown words:             {len(candidates)}')
    print(f'Selected (top {TOP_N}):         {len(result)}')
    print(f'With meanings:             {sum(1 for e in result if e["meaning"])}')
    top5 = result[:5]
    top5_str = ', '.join(f'{e["word"]} ({e["frequency_in_section"]}x)' for e in top5)
    print(f'Top 5: {top5_str}')
    print(f'index.html written to {BASE_DIR / "index.html"}')


if __name__ == '__main__':
    main()
