---
name: epub-word-analysis
description: Analyze a Japanese epub file to find the top 100 high-frequency unknown vocabulary with WaniKani kanji mnemonics. Prioritises words whose kanji all appear in WaniKani. Use when the user wants to study vocabulary from a Japanese book.
---

# Japanese EPUB Word Frequency Analyzer

Given a Japanese epub and Migaku known-words data, produce a ranked JSON list of
the **top 100** unknown words — kanji words are prioritised by WaniKani coverage,
and frequent kana-only words are included too — with frequency, reading, and
WaniKani kanji meaning mnemonics where applicable.

## Prerequisites

Ask the user for:
- **WaniKani API token** — required before step 5
- **EPUB path** — local path to the book file
- **`BASE_DIR`** — absolute path to the project directory

## Token Efficiency Rules (follow strictly)
- **Never** fetch all WaniKani subjects. Use the `slugs` parameter with only kanji in the final word list.
- Filter to **freq >= 2** before the WaniKani call (kana-only words pass too — they just skip the kanji lookup).
- **Two WaniKani API calls**: one for kanji (batched, 100 slugs per request), one for vocabulary (meanings).
- Use the tokenisation cache (`data/word_counts_<hash>.json`) — skip re-tokenising if it exists.
- Do NOT echo `result.json` back to the user — it is too large. Report stats only.
- **result.json schema is lean**: only store `character`, `meaning`, `reading`, `meaning_mnemonic` per kanji. No `reading_mnemonic`, no `scene_hook`.
- Filter uses **two sources**: `migaku_data/known_words.json` (primary — 7000+ SRS words from srs.db) AND `data/jp_top1000.txt` (secondary — ~850 common vocab the user knows but hasn't tracked in Migaku). Both are always applied.

---

## Workflow

Run `analyze_epub.py` which handles all steps:
```bash
cd <BASE_DIR>
python analyze_epub.py <EPUB_PATH> <WK_TOKEN>
```

The script does the following internally:

### 1. Find the data

Locate in `<BASE_DIR>`:
- The `.epub` file to analyze
- `migaku_data/known_words.json` — output from `migaku-fetch` skill
- `data/epub_text_<hash>.txt` — epub text cache (auto-created on first run)
- `data/word_counts_<hash>.txt` — tokenisation cache (auto-created on first run)

### 2. Extract text from epub (cached by epub MD5 hash)

```python
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
import hashlib

cache_key  = hashlib.md5(epub_path.read_bytes()).hexdigest()[:8]
cache_file = DATA_DIR / f'epub_text_{cache_key}.txt'

if cache_file.exists():
    text = cache_file.read_text(encoding='utf-8')
else:
    n_sections = None  # None = entire book; pass an int to cap sections
    book = epub.read_epub(epub_path)
    texts, count = [], 0
    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ITEM_DOCUMENT:
            t = BeautifulSoup(item.get_content(), 'lxml').get_text()
            if t.strip():
                texts.append(t); count += 1
        if n_sections is not None and count >= n_sections: break
    text = '\n'.join(texts)
    cache_file.write_text(text, encoding='utf-8')
```

### 3. Tokenize with janome (cached by epub hash)

```python
from janome.tokenizer import Tokenizer
from collections import Counter
import json

cache_file = DATA_DIR / f'word_counts_{cache_key}.json'

if cache_file.exists():
    cached = json.loads(cache_file.read_text(encoding='utf-8'))
    word_count, word_reading = Counter(cached['counts']), cached['readings']
else:
    KEEP_POS = {'名詞', '動詞', '形容詞', '副詞'}
    tokenizer = Tokenizer()
    word_count = Counter()
    word_reading = {}

    for t in tokenizer.tokenize(text):
        pos = t.part_of_speech.split(',')[0]
        base = t.base_form
        # Kana-only bases are kept too — filtered later by frequency/known-word checks,
        # not blanket-excluded here.
        if pos in KEEP_POS and base and base != '*' and len(base) >= 2:
            word_count[base] += 1
            if base not in word_reading and t.reading and t.reading != '*':
                word_reading[base] = t.reading

    cache_file.write_text(
        json.dumps({'counts': dict(word_count), 'readings': word_reading},
                   ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
```

### 4. Filter against known words (Migaku + common vocab)

```python
with open('migaku_data/known_words.json', encoding='utf-8') as f:
    raw = json.load(f)
# migaku-fetch outputs objects with dictForm as the word key — NOT 'word'
known = {item['dictForm'] if isinstance(item, dict) else item for item in raw}
known.discard('')

# Also filter against jp_top1000.txt (basic vocab the user knows but hasn't tracked)
top1k_file = DATA_DIR / 'jp_top1000.txt'
if top1k_file.exists():
    common = {l.strip() for l in top1k_file.read_text(encoding='utf-8').splitlines() if l.strip()}
    known |= common

candidates = [
    (w, cnt) for w, cnt in word_count.most_common()
    if w not in known and cnt >= 2
]
```

### 5. Fetch WaniKani kanji data (batched — 100 slugs per request)

`wk_token` defaults to the `WK_TOKEN` constant in `analyze_epub.py`; can also be
passed as `sys.argv[2]`. **Do NOT send all kanji in one request** — large slug lists
cause 503 errors. Batch at 100 and retry on 503.

```python
import requests, time

all_kanji = sorted({c for w, _ in candidates for c in w
                    if ord('一') <= ord(c) <= ord('鿿')})

wk_kanji = {}
for i in range(0, len(all_kanji), 100):
    batch = all_kanji[i:i + 100]
    for attempt in range(4):
        resp = requests.get(
            'https://api.wanikani.com/v2/subjects',
            params={'types': 'kanji', 'slugs': ','.join(batch)},
            headers={'Authorization': f'Bearer {wk_token}'},
            timeout=30
        )
        if resp.status_code == 503:
            time.sleep(2 ** attempt); continue
        resp.raise_for_status()
        for s in resp.json()['data']:
            wk_kanji[s['data']['characters']] = s['data']
        time.sleep(0.3)
        break
```

### 5.5. WK-focused ranking — prefer words where ALL kanji are in WaniKani

```python
TOP_N = 100

tier1, tier2, tier_kana = [], [], []
for w, cnt in candidates:
    chars = [c for c in w if ord('一') <= ord(c) <= ord('鿿')]
    if not chars:
        tier_kana.append((w, cnt))   # kana-only word — no kanji mnemonics, still useful
        continue
    in_wk = sum(1 for c in chars if c in wk_kanji)
    if in_wk == len(chars):
        tier1.append((w, cnt))   # all kanji in WK — preferred
    elif in_wk > 0:
        tier2.append((w, cnt))   # some kanji in WK
    # Words with kanji but zero WK coverage are dropped

final_words = (tier1 + tier2 + tier_kana)[:TOP_N]  # tier1, then tier2, then kana-only
```

### 6. Fetch WaniKani vocabulary meanings (second targeted call)

```python
word_slugs = ','.join(w for w, _ in final_words)
resp_vocab = requests.get(
    'https://api.wanikani.com/v2/subjects',
    params={'types': 'vocabulary', 'slugs': word_slugs},
    headers={'Authorization': f'Bearer {wk_token}'},
    timeout=30
)
resp_vocab.raise_for_status()
wk_vocab = {s['data']['characters']: s['data'] for s in resp_vocab.json()['data']}
```

### 7. Build result.json — lean schema

Only store what the UI actually needs. Do NOT store `reading_mnemonic` or `scene_hook` — they bloat the file and are not displayed.

```python
result = []
for word, freq in final_words:
    wv = wk_vocab.get(word, {})
    meaning = next((m['meaning'] for m in wv.get('meanings', []) if m.get('primary')), None)

    kanji_list = []
    for c in word:
        if not (ord('一') <= ord(c) <= ord('鿿')): continue
        d = wk_kanji.get(c, {})
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
```

### 7.5. Jisho fallback for words not in WK vocabulary

```python
import time

missing = [e for e in result if e['meaning'] is None]
for entry in missing:
    try:
        r = requests.get('https://jisho.org/api/v1/search/words',
                         params={'keyword': entry['word']}, timeout=10)
        data = r.json().get('data', [])
        if data and data[0].get('senses'):
            entry['meaning'] = data[0]['senses'][0]['english_definitions'][0]
    except Exception:
        pass
    time.sleep(0.25)

still_missing = [e['word'] for e in result if e['meaning'] is None]
if still_missing:
    print(f'[warn] {len(still_missing)} words still have no meaning: {still_missing}')

with open('result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
```

**If words are still null after Jisho**: do NOT use a kanji-composition fallback and do NOT
call an external API. Instead, just report the list to the user. Claude (in conversation)
can instantly generate real meanings — paste the `[warn]` list and ask Claude to fill them:

```python
# After the pipeline, patch result.json directly:
meanings = {
    "迷宮": "labyrinth / dungeon",
    "転生者": "reincarnated person",
    # ...
}
for e in result:
    if not e['meaning'] and e['word'] in meanings:
        e['meaning'] = meanings[e['word']]
```

### 8. Generate index.html

```python
from build_html import build_html
build_html(result, BASE_DIR / 'index.html')
```

### 9. Report stats only — do NOT echo result.json

```
Words analysed (epub):     <total tokens>
Unknown kanji-words:       <N candidates>
WK-focused (top 100):      <N final>
With meanings:             <N>
Top 5: <word> (<freq>x), ...
index.html written to <path>
```

---

## Output schema (result.json)

```json
[
  {
    "word": "取得",
    "reading": "しゅとく",
    "meaning": "acquisition",
    "frequency_in_section": 42,
    "kanji": [
      {
        "character": "取",
        "meaning": "take",
        "reading": "しゅ",
        "meaning_mnemonic": "<radical>ear</radical> on a <radical>stool</radical>..."
      }
    ]
  }
]
```

- Sorted by `frequency_in_section` descending within WK tier
- `kanji: []` for frequent kana-only words (included after kanji-tier words)
- `meaning: null` if neither WK vocab nor Jisho have an entry
- No `reading_mnemonic` field — not stored, not needed
- No `scene_hook` field — not stored, not needed

## Dependencies

```
ebooklib  beautifulsoup4  lxml  janome  requests
```
