#!/usr/bin/env python3
"""Patch result.json word meanings using context from the source book.

Jisho/WaniKani lookups miss compound nouns, skill names, and the story's
invented monster/character names entirely. This fills those gaps with
meanings read directly from the book's actual usage rather than a generic
dictionary fallback.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
RESULT_FILE = BASE_DIR / 'result.json'

MEANINGS = {
    "操糸": "thread manipulation (skill)",
    "巨猿": "giant ape",
    "蜘蛛糸": "spider thread",
    "突破": "breakthrough",
    "猿たち": "the apes",
    "鑑定石": "appraisal stone",
    "スモールレッサータラテクト": "Small Lesser Taratect (spider species)",
    "人族": "human race",
    "クレベア": "Klevea (character name)",
    "クモーニングスター": "Kumorning Star (sticky-thread flail weapon)",
    "闘法": "combat technique",
    "エルローランダネル": "Elro Randanel (monster)",
    "フィンジゴアット": "Finzigoat (monster)",
    "猿ども": "those apes",
    "公爵家": "ducal family",
    "麻痺": "paralysis",
    "一発": "one shot",
    "ゴム糸": "rubber thread",
    "エルローフェレクト": "Elro Ferect (monster)",
    "粘着糸": "sticky thread",
}


def main():
    result = json.loads(RESULT_FILE.read_text(encoding='utf-8'))
    patched = 0
    found = set()
    for entry in result:
        word = entry.get('word')
        if word in MEANINGS:
            entry['meaning'] = MEANINGS[word]
            patched += 1
            found.add(word)

    RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    missing = set(MEANINGS) - found
    print(f'[ok] patched {patched} word meanings')
    if missing:
        print(f'[warn] {len(missing)} entries had no matching word in result.json: {sorted(missing)}')


if __name__ == '__main__':
    main()
