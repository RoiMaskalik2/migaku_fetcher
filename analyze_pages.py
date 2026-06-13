#!/usr/bin/env python3
"""analyze_pages.py — Tokenise spider_next_pages.txt and build a study HTML."""

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

from analyze_epub import (
    tokenize, filter_known, fetch_wanikani, rank_by_wanikani,
    fetch_wk_vocab, build_result, enrich_jisho, WK_TOKEN,
)
from build_html import build_html

BASE_DIR   = Path(__file__).parent
PAGES_FILE = BASE_DIR / 'migaku_data' / 'spider_next_pages.txt'
OUT_JSON   = BASE_DIR / 'result_spider_pages.json'
OUT_HTML   = BASE_DIR / 'spider_next_pages.html'


def main():
    if not PAGES_FILE.exists():
        print(f'[error] {PAGES_FILE} not found — run migaku_fetch.py first')
        sys.exit(1)

    text = PAGES_FILE.read_text(encoding='utf-8')
    print(f'[ok] loaded {len(text):,} chars from {PAGES_FILE.name}')

    # tokenise() accepts any Path for cache-key hashing, not just epubs
    word_count, word_reading = tokenize(text, PAGES_FILE)

    candidates = filter_known(word_count, word_reading)

    wk_kanji = fetch_wanikani(candidates, WK_TOKEN)

    final_words = rank_by_wanikani(candidates, wk_kanji)
    print(f'[ok] selected top {len(final_words)} WK-focused words')

    wk_vocab = fetch_wk_vocab([w for w, _ in final_words], WK_TOKEN)

    result = build_result(final_words, wk_kanji, wk_vocab, word_reading)

    result = enrich_jisho(result)

    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[ok] result JSON written → {OUT_JSON}')

    build_html(result, OUT_HTML, title='蜘蛛ですが、なにか？ · Next Pages')


if __name__ == '__main__':
    main()
