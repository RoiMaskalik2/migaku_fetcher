#!/usr/bin/env python3
"""
analyze_srt.py — Produces result JSON + HTML from a directory of Japanese SRT files.

Usage:
    python analyze_srt.py <srt_dir> [output_json] [output_html] [title]

Example:
    python analyze_srt.py subtitles/fma/s01 result_fma_s01.json fma_s01.html "FMA Brotherhood S1"
"""

import sys, json, re, time, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from collections import Counter

BASE_DIR    = Path(__file__).parent
MIGAKU_DATA = BASE_DIR / 'migaku_data'
DATA_DIR    = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

WK_TOKEN = "d80065d9-7717-4d27-948c-2ad657faa924"

TOP_N    = 100
MIN_FREQ = 2

KANJI_MIN = ord('一')
KANJI_MAX = ord('鿿')

TIMESTAMP_RE = re.compile(r'^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}')
INDEX_RE     = re.compile(r'^\d+\s*$')


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_kanji(c: str) -> bool:
    return KANJI_MIN <= ord(c) <= KANJI_MAX


def has_kanji(word: str) -> bool:
    return any(is_kanji(c) for c in word)


def kata_to_hira(text: str) -> str:
    return ''.join(
        chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c
        for c in text
    )


def srt_dir_hash(srt_dir: Path) -> str:
    h = hashlib.md5()
    for f in sorted(srt_dir.glob('*.srt')):
        h.update(f.read_bytes())
    return h.hexdigest()[:8]


# ── Step 1: Extract text from SRT files ───────────────────────────────────────

def load_text(srt_dir: Path) -> str:
    srt_files = sorted(srt_dir.glob('*.srt'))
    if not srt_files:
        print(f'[error] no .srt files found in {srt_dir}')
        sys.exit(1)

    cache_key  = srt_dir_hash(srt_dir)
    cache_file = DATA_DIR / f'srt_text_{cache_key}.txt'

    if cache_file.exists():
        print(f'[skip] SRT text cache found ({cache_file.name})')
        return cache_file.read_text(encoding='utf-8')

    lines = []
    for srt_file in srt_files:
        raw = srt_file.read_text(encoding='utf-8-sig', errors='replace')
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if INDEX_RE.match(line):
                continue
            if TIMESTAMP_RE.match(line):
                continue
            # Strip parenthetical speaker labels like （マスタング）at line start/end
            line = re.sub(r'^（[^）]*）', '', line).strip()
            line = re.sub(r'（[^）]*）$', '', line).strip()
            if line:
                lines.append(line)

    text = '\n'.join(lines)
    cache_file.write_text(text, encoding='utf-8')
    print(f'[ok] SRT text extracted ({len(srt_files)} files, {len(text):,} chars)')
    return text


# ── Step 2: Tokenise ──────────────────────────────────────────────────────────

def tokenize(text: str, cache_key: str):
    cache_file = DATA_DIR / f'word_counts_{cache_key}.json'

    if cache_file.exists():
        print(f'[skip] tokenisation cache found ({cache_file.name})')
        cached = json.loads(cache_file.read_text(encoding='utf-8'))
        readings = {w: kata_to_hira(r) for w, r in cached['readings'].items()}
        return Counter(cached['counts']), readings

    from janome.tokenizer import Tokenizer
    KEEP_POS = {'名詞', '動詞', '形容詞', '副詞'}
    NOUN_COMPOUND_TYPES = {'一般', 'サ変接続', '固有名詞', '副詞可能', '数', 'ナイ形容詞語幹'}

    def _keep(base: str) -> bool:
        return (base and base != '*'
                and not all('ぁ' <= c <= 'ゟ' for c in base))

    print('[...] tokenising (first run, may take ~60s)...')
    tokenizer    = Tokenizer()
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

def filter_known(word_count: Counter, word_reading: dict) -> list:
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


# ── Step 4: Fetch WaniKani kanji data ────────────────────────────────────────

def fetch_wanikani(candidates: list, wk_token: str) -> dict:
    import requests
    headers  = {'Authorization': f'Bearer {wk_token}'}
    all_kanji = sorted({c for w, _ in candidates for c in w if is_kanji(c)})
    if not all_kanji:
        return {}

    print(f'[wk] fetching {len(all_kanji)} kanji subjects...')
    wk_kanji   = {}
    batch_size = 100
    for i in range(0, len(all_kanji), batch_size):
        batch = all_kanji[i:i + batch_size]
        for attempt in range(4):
            resp = requests.get(
                'https://api.wanikani.com/v2/subjects',
                params={'types': 'kanji', 'slugs': ','.join(batch)},
                headers=headers, timeout=30
            )
            if resp.status_code == 503:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            for s in resp.json()['data']:
                wk_kanji[s['data']['characters']] = s['data']
            time.sleep(0.3)
            break

    print(f'[wk] got {len(wk_kanji)}/{len(all_kanji)} kanji in WaniKani')
    return wk_kanji


def fetch_wk_vocab(words: list, wk_token: str) -> dict:
    import requests
    if not words:
        return {}

    headers = {'Authorization': f'Bearer {wk_token}'}
    slugs   = ','.join(words[:200])
    print(f'[wk] fetching vocabulary meanings for up to {len(words)} words...')
    for attempt in range(4):
        resp = requests.get(
            'https://api.wanikani.com/v2/subjects',
            params={'types': 'vocabulary', 'slugs': slugs},
            headers=headers, timeout=30
        )
        if resp.status_code == 503:
            time.sleep(2 ** attempt)
            continue
        break
    resp.raise_for_status()
    wk_vocab = {s['data']['characters']: s['data'] for s in resp.json()['data']}
    print(f'[wk] got vocab meanings for {len(wk_vocab)}/{len(words)} words')
    return wk_vocab


# ── Step 5: WaniKani-focused ranking ─────────────────────────────────────────

def rank_by_wanikani(candidates: list, wk_kanji: dict) -> list:
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


# ── Step 6: Build result entries ─────────────────────────────────────────────

def build_result(words: list, wk_kanji: dict, wk_vocab: dict, word_reading: dict) -> list:
    result = []
    for word, freq in words:
        wv      = wk_vocab.get(word, {})
        meaning = None
        if wv:
            wv_meanings = wv.get('meanings', [])
            meaning = next((m['meaning'] for m in wv_meanings if m.get('primary')), None)

        kanji_list = []
        for c in word:
            if not is_kanji(c):
                continue
            d        = wk_kanji.get(c, {})
            meanings = d.get('meanings', [])
            readings = d.get('readings', [])
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


# ── Step 7: Jisho fallback ───────────────────────────────────────────────────

def enrich_jisho(result: list) -> list:
    import requests
    missing = [e for e in result if e['meaning'] is None]
    if not missing:
        return result

    print(f'[jisho] enriching {len(missing)} words without WK meanings...')
    for entry in missing:
        try:
            r = requests.get(
                'https://jisho.org/api/v1/search/words',
                params={'keyword': entry['word']}, timeout=10
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
        print('Usage: python analyze_srt.py <srt_dir> [output_json] [output_html] [title]')
        sys.exit(1)

    srt_dir     = Path(sys.argv[1])
    out_json    = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE_DIR / 'result_srt.json'
    out_html    = Path(sys.argv[3]) if len(sys.argv) > 3 else BASE_DIR / 'srt_vocab.html'
    title       = sys.argv[4] if len(sys.argv) > 4 else '日本語'
    wk_token    = WK_TOKEN

    if not srt_dir.exists():
        print(f'[error] directory not found: {srt_dir}')
        sys.exit(1)

    cache_key = srt_dir_hash(srt_dir)

    # 1. Extract text
    text = load_text(srt_dir)

    # 2. Tokenise
    word_count, word_reading = tokenize(text, cache_key)

    # 3. Filter
    candidates = filter_known(word_count, word_reading)

    # 4. Fetch WK kanji
    wk_kanji = fetch_wanikani(candidates, wk_token)

    # 5. Rank & select top 100
    final_words = rank_by_wanikani(candidates, wk_kanji)
    print(f'[ok] selected top {len(final_words)} WK-focused words')

    # 6. Fetch WK vocab meanings
    wk_vocab = fetch_wk_vocab([w for w, _ in final_words], wk_token)

    # 7. Build result
    result = build_result(final_words, wk_kanji, wk_vocab, word_reading)

    # 8. Jisho fallback
    result = enrich_jisho(result)

    # 9. Save JSON
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[ok] {out_json.name} written ({len(result)} words)')

    # 10. Generate HTML
    from build_html import build_html
    build_html(result, out_html, title)

    # Stats
    print('\n── Stats ──────────────────────────────')
    print(f'Words in subtitles:        {sum(word_count.values()):,}')
    print(f'Unknown kanji-words:       {len(candidates)}')
    print(f'WK-focused (top {TOP_N}):       {len(result)}')
    print(f'With meanings:             {sum(1 for e in result if e["meaning"])}')
    top5 = result[:5]
    top5_str = ', '.join(f'{e["word"]} ({e["frequency_in_section"]}x)' for e in top5)
    print(f'Top 5: {top5_str}')
    print(f'HTML written to {out_html}')


if __name__ == '__main__':
    main()
