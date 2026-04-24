#!/usr/bin/env python3
"""
analyze_srt.py — Produces result.json + index.html from Japanese SRT subtitle files.

Usage:
    python analyze_srt.py <srt_file> [<srt_file2> ...] --wk-token <TOKEN>

Examples:
    python analyze_srt.py episode01.srt --wk-token abc123
    python analyze_srt.py subs/ep01.srt subs/ep02.srt subs/ep03.srt --wk-token abc123
"""

import sys, re, json, time, hashlib, argparse
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from collections import Counter

BASE_DIR    = Path(__file__).parent
MIGAKU_DATA = BASE_DIR / 'migaku_data'
DATA_DIR    = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

TOP_N    = 100
MIN_FREQ = 2

KANJI_MIN = ord('一')
KANJI_MAX = ord('鿿')


def is_kanji(c: str) -> bool:
    return KANJI_MIN <= ord(c) <= KANJI_MAX


def has_kanji(word: str) -> bool:
    return any(is_kanji(c) for c in word)


def kata_to_hira(text: str) -> str:
    return ''.join(
        chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c
        for c in text
    )


# ── Step 1: Parse SRT files ───────────────────────────────────────────────────

def parse_srt(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('shift-jis', errors='replace')

    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\{[^}]+\}', '', text)
    return text


def load_srt_text(srt_paths: list[Path]) -> str:
    parts = []
    for p in srt_paths:
        if not p.exists():
            print(f'[error] file not found: {p}')
            sys.exit(1)
        parts.append(parse_srt(p))
        print(f'[ok] parsed {p.name}')
    combined = '\n'.join(parts)
    print(f'[ok] combined {len(srt_paths)} file(s), {len(combined):,} chars total')
    return combined


# ── Step 2: Tokenise (cached by content hash) ─────────────────────────────────

def tokenize(text: str) -> tuple[Counter, dict]:
    cache_key  = hashlib.md5(text.encode('utf-8')).hexdigest()[:8]
    cache_file = DATA_DIR / f'srt_counts_{cache_key}.json'

    if cache_file.exists():
        print(f'[skip] tokenisation cache found ({cache_file.name})')
        cached = json.loads(cache_file.read_text(encoding='utf-8'))
        return Counter(cached['counts']), {w: kata_to_hira(r) for w, r in cached['readings'].items()}

    from janome.tokenizer import Tokenizer
    KEEP_POS = {'名詞', '動詞', '形容詞', '副詞'}
    NOUN_COMPOUND_TYPES = {'一般', 'サ変接続', '固有名詞', '副詞可能', '数', 'ナイ形容詞語幹'}

    def _keep(base: str) -> bool:
        return (base and base != '*' and len(base) >= 2
                and not all('ぁ' <= c <= 'ゟ' for c in base))

    print('[...] tokenising (first run, may take ~60s)...')
    tokenizer  = Tokenizer()
    word_count   = Counter()
    word_reading = {}
    noun_buf     = None  # (base_str, reading_str) | None

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

    flush()

    cache_file.write_text(
        json.dumps({'counts': dict(word_count), 'readings': word_reading},
                   ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f'[ok] tokenised: {len(word_count)} unique words')
    return word_count, word_reading


# ── Step 3: Filter against known words ───────────────────────────────────────

def filter_known(word_count: Counter) -> list[tuple[str, int]]:
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
        print(f'[ok] {len(known)} known words from Migaku SRS')
    else:
        print('[info] no known_words.json found — filtering by jp_top1000.txt only')

    common = set()
    if top1k_file.exists():
        common = {l.strip() for l in top1k_file.read_text(encoding='utf-8').splitlines() if l.strip()}
        print(f'[ok] {len(common)} common words from jp_top1000.txt')

    candidates = [
        (w, cnt) for w, cnt in word_count.most_common()
        if w not in known and w not in common and cnt >= MIN_FREQ and has_kanji(w)
    ]
    print(f'[ok] {len(candidates)} unknown kanji-words with freq >= {MIN_FREQ}')
    return candidates


# ── Step 4: Fetch WaniKani kanji data ─────────────────────────────────────────

def fetch_wanikani_kanji(candidates: list[tuple[str, int]], wk_token: str) -> dict:
    import requests

    all_kanji = sorted({c for w, _ in candidates for c in w if is_kanji(c)})
    if not all_kanji:
        return {}

    print(f'[wk] fetching {len(all_kanji)} kanji subjects...')
    resp = requests.get(
        'https://api.wanikani.com/v2/subjects',
        params={'types': 'kanji', 'slugs': ','.join(all_kanji)},
        headers={'Authorization': f'Bearer {wk_token}'},
        timeout=30
    )
    resp.raise_for_status()
    wk_kanji = {s['data']['characters']: s['data'] for s in resp.json()['data']}
    print(f'[wk] got {len(wk_kanji)}/{len(all_kanji)} kanji in WaniKani')
    return wk_kanji


# ── Step 5: WK-focused ranking ────────────────────────────────────────────────

def rank_by_wanikani(candidates: list[tuple[str, int]], wk_kanji: dict) -> list[tuple[str, int]]:
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

    print(f'[wk] tier1 (all kanji in WK): {len(tier1)}, tier2 (partial): {len(tier2)}')
    return (tier1 + tier2)[:TOP_N]


# ── Step 6: Fetch WK vocabulary meanings ─────────────────────────────────────

def fetch_wanikani_vocab(words: list[str], wk_token: str) -> dict:
    import requests
    if not words:
        return {}

    print(f'[wk] fetching vocabulary meanings for {len(words)} words...')
    resp = requests.get(
        'https://api.wanikani.com/v2/subjects',
        params={'types': 'vocabulary', 'slugs': ','.join(words[:200])},
        headers={'Authorization': f'Bearer {wk_token}'},
        timeout=30
    )
    resp.raise_for_status()
    wk_vocab = {s['data']['characters']: s['data'] for s in resp.json()['data']}
    print(f'[wk] got vocab meanings for {len(wk_vocab)}/{len(words)} words')
    return wk_vocab


# ── Step 7: Build result entries ──────────────────────────────────────────────

def build_result(words: list[tuple[str, int]], wk_kanji: dict, wk_vocab: dict,
                 word_reading: dict) -> list[dict]:
    result = []
    for word, freq in words:
        wv = wk_vocab.get(word, {})
        meaning = next((m['meaning'] for m in wv.get('meanings', []) if m.get('primary')), None)

        kanji_list = []
        for c in word:
            if not is_kanji(c):
                continue
            d  = wk_kanji.get(c, {})
            pm = next((m['meaning'] for m in d.get('meanings', []) if m.get('primary')), None)
            pr = next((r['reading'] for r in d.get('readings', []) if r.get('primary')), None)
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


# ── Step 8: Jisho fallback ────────────────────────────────────────────────────

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
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Analyze Japanese SRT subtitle files.')
    parser.add_argument('srt_files', nargs='+', help='Path(s) to .srt file(s)')
    parser.add_argument('--wk-token', required=True, help='WaniKani API token (v2)')
    args = parser.parse_args()

    srt_paths = [Path(p) for p in args.srt_files]
    wk_token  = args.wk_token

    # 1. Parse SRT files
    text = load_srt_text(srt_paths)

    # 2. Tokenise
    word_count, word_reading = tokenize(text)

    # 3. Filter
    candidates = filter_known(word_count)

    # 4. Fetch WK kanji
    wk_kanji = fetch_wanikani_kanji(candidates, wk_token)

    # 5. Rank
    final_words = rank_by_wanikani(candidates, wk_kanji)
    print(f'[ok] selected top {len(final_words)} WK-focused words')

    # 6. Fetch WK vocab meanings
    wk_vocab = fetch_wanikani_vocab([w for w, _ in final_words], wk_token)

    # 7. Build result
    result = build_result(final_words, wk_kanji, wk_vocab, word_reading)

    # 8. Jisho fallback
    result = enrich_jisho(result)

    # 9. Save result.json — preserve meanings from any prior run
    out = BASE_DIR / 'result.json'
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding='utf-8'))
            old_meanings = {e['word']: e['meaning'] for e in old if e.get('meaning')}
            for entry in result:
                if entry['meaning'] is None and entry['word'] in old_meanings:
                    entry['meaning'] = old_meanings[entry['word']]
        except Exception:
            pass
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[ok] result.json written ({len(result)} words)')

    # 10. Generate index.html
    from build_html import build_html
    build_html(result, BASE_DIR / 'index.html')

    # Stats
    print('\n── Stats ──────────────────────────────')
    print(f'SRT files parsed:          {len(srt_paths)}')
    print(f'Words tokenised:           {sum(word_count.values()):,}')
    print(f'Unknown kanji-words:       {len(candidates)}')
    print(f'WK-focused (top {TOP_N}):       {len(result)}')
    print(f'With meanings:             {sum(1 for e in result if e["meaning"])}')
    top5     = result[:5]
    top5_str = ', '.join(f'{e["word"]} ({e["frequency_in_section"]}x)' for e in top5)
    print(f'Top 5: {top5_str}')
    print(f'index.html written to {BASE_DIR / "index.html"}')


if __name__ == '__main__':
    main()
