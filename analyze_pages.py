#!/usr/bin/env python3
"""analyze_pages.py — Tokenise spider_next_pages.txt and build a study HTML."""

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

from analyze_epub import (
    tokenize, filter_known, rank_by_wanikani, fetch_wanikani_with_fallback,
    fetch_wk_vocab, build_result, enrich_jisho, epub_hash,
    WK_TOKEN, TOP_N, is_kanji,
)
from build_html import build_html

BASE_DIR   = Path(__file__).parent
PAGES_FILE = BASE_DIR / 'migaku_data' / 'spider_next_pages.txt'
OUT_JSON   = BASE_DIR / 'result_spider_pages.json'
OUT_HTML   = BASE_DIR / 'spider_next_pages.html'


def rank_by_frequency(candidates, wk_kanji):
    """Rank by frequency; use WK coverage only to prefer better-covered words."""
    tier1, tier2, tier3, tier_kana = [], [], [], []
    for w, cnt in candidates:
        chars = [c for c in w if is_kanji(c)]
        if not chars:
            tier_kana.append((w, cnt))
            continue
        in_wk = sum(1 for c in chars if c in wk_kanji)
        if in_wk == len(chars):
            tier1.append((w, cnt))
        elif in_wk > 0:
            tier2.append((w, cnt))
        else:
            tier3.append((w, cnt))
    result = tier1 + tier2 + tier3 + tier_kana
    print(f'[rank] tier1={len(tier1)} tier2={len(tier2)} tier3={len(tier3)} '
          f'kana-only={len(tier_kana)}')
    return result[:TOP_N]


def main():
    if not PAGES_FILE.exists():
        print(f'[error] {PAGES_FILE} not found — run migaku_fetch.py first')
        sys.exit(1)

    text = PAGES_FILE.read_text(encoding='utf-8')
    print(f'[ok] loaded {len(text):,} chars from {PAGES_FILE.name}')

    word_count, word_reading = tokenize(text, epub_hash(PAGES_FILE))

    candidates = filter_known(word_count, word_reading)

    wk_kanji = fetch_wanikani_with_fallback(candidates, WK_TOKEN)

    # Use frequency+WK-coverage ranking (includes tier3 when WK is unavailable)
    final_words = rank_by_frequency(candidates, wk_kanji)
    print(f'[ok] selected top {len(final_words)} words')

    try:
        wk_vocab = fetch_wk_vocab([w for w, _ in final_words], WK_TOKEN)
    except Exception as e:
        print(f'[warn] WK vocab unavailable ({e}) — meanings from Jisho only')
        wk_vocab = {}

    result = build_result(final_words, wk_kanji, wk_vocab, word_reading)

    result = enrich_jisho(result)

    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[ok] result JSON written → {OUT_JSON}')

    build_html(result, OUT_HTML, title='蜘蛛ですが、なにか？ · Next Pages')


if __name__ == '__main__':
    main()
