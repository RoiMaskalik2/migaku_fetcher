---
name: epub-word-analysis
description: Analyze a Japanese epub file to find the top 100 high-frequency unknown vocabulary with WaniKani kanji mnemonics. Prioritises words whose kanji all appear in WaniKani. Use when the user wants to study vocabulary from a Japanese book.
---

# Japanese EPUB Word Frequency Analyzer

Given a Japanese epub and Migaku known-words data, produce a ranked JSON list of
the **top 100** unknown words (kanji must be in WaniKani) with frequency, reading,
WaniKani kanji mnemonics, and scene hooks.

## Prerequisites

Ask the user for:
- **WaniKani API token** — required before step 5
- **EPUB path** — local path to the book file
- **`BASE_DIR`** — absolute path to the project directory

## Token Efficiency Rules (follow strictly)
- **Never** fetch all WaniKani subjects. Use the `slugs` parameter with only kanji in the final word list.
- Filter to **freq >= 2 AND has kanji** before the WaniKani call.
- **Two WaniKani API calls**: one for kanji, one for vocabulary (meanings).
- Use the tokenisation cache (`data/word_counts_<hash>.json`) — skip re-tokenising if it exists.
- Do NOT echo `result.json` back to the user — it is too large. Report stats only.

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
- `data/jp_top1000.txt` — common words to exclude (create empty if missing)

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
    n_sections = 20  # increase for larger coverage
    book = epub.read_epub(epub_path)
    texts, count = [], 0
    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ITEM_DOCUMENT:
            t = BeautifulSoup(item.get_content(), 'lxml').get_text()
            if t.strip():
                texts.append(t); count += 1
        if count >= n_sections: break
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
        if (pos in KEEP_POS and base and base != '*' and len(base) >= 2
                and not all('ぁ' <= c <= 'ゟ' for c in base)):
            word_count[base] += 1
            if base not in word_reading and t.reading and t.reading != '*':
                word_reading[base] = t.reading

    cache_file.write_text(
        json.dumps({'counts': dict(word_count), 'readings': word_reading},
                   ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
```

### 4. Filter against known words

```python
with open('migaku_data/known_words.json', encoding='utf-8') as f:
    raw = json.load(f)
# migaku-fetch outputs objects with dictForm as the word key — NOT 'word'
known = {item['dictForm'] if isinstance(item, dict) else item for item in raw}

with open('data/jp_top1000.txt', encoding='utf-8') as f:
    top1000 = set(l.strip() for l in f if l.strip())

def has_kanji(word):
    return any(ord('一') <= ord(c) <= ord('鿿') for c in word)

# Keep only kanji-containing words with freq >= 2 (kana-only words excluded)
candidates = [
    (w, cnt) for w, cnt in word_count.most_common()
    if w not in known and w not in top1000 and cnt >= 2 and has_kanji(w)
]
```

### 5. Fetch WaniKani kanji data (single targeted call)

`wk_token` is passed as a CLI argument.

```python
import requests

all_kanji = sorted({c for w, _ in candidates for c in w
                    if ord('一') <= ord(c) <= ord('鿿')})

resp = requests.get(
    'https://api.wanikani.com/v2/subjects',
    params={'types': 'kanji', 'slugs': ','.join(all_kanji)},
    headers={'Authorization': f'Bearer {wk_token}'},
    timeout=30
)
resp.raise_for_status()
wk_kanji = {s['data']['characters']: s['data'] for s in resp.json()['data']}
```

### 5.5. WK-focused ranking — prefer words where ALL kanji are in WaniKani

```python
TOP_N = 100

tier1, tier2 = [], []
for w, cnt in candidates:
    chars = [c for c in w if ord('一') <= ord(c) <= ord('鿿')]
    in_wk = sum(1 for c in chars if c in wk_kanji)
    if in_wk == len(chars):
        tier1.append((w, cnt))   # all kanji in WK — preferred
    elif in_wk > 0:
        tier2.append((w, cnt))   # some kanji in WK
    # Words with zero WK kanji are dropped

final_words = (tier1 + tier2)[:TOP_N]  # tier1 first (by freq), then tier2
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

### 7. Build result.json — all fields required by japanese-vocab-learner

Extract scene hooks from mnemonic first sentences for visualization:

```python
import re

def extract_scene_hook(mnemonic_text):
    if not mnemonic_text: return None
    clean = re.sub(r'<[^>]+>', '', mnemonic_text).strip()
    parts = re.split(r'(?<=[.!?])\s+', clean)
    hook = parts[0].strip() if parts else ''
    return hook[:200] if len(hook) > 15 else None

result = []
for word, freq in final_words:
    # Word meaning: WK vocab first, Jisho fallback (step 7.5)
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
        mm = d.get('meaning_mnemonic')
        rm = d.get('reading_mnemonic')
        kanji_list.append({
            'character':        c,
            'meaning':          pm,
            'reading':          pr,
            'meaning_mnemonic': mm,
            'reading_mnemonic': rm,
            'scene_hook':       extract_scene_hook(mm),
        })
    result.append({
        'word':                 word,
        'reading':              word_reading.get(word, ''),
        'meaning':              meaning,   # populated by step 7.5 if WK vocab misses
        'frequency_in_section': freq,
        'kanji':                kanji_list,
    })
```

### 7.5. Jisho fallback for words not in WK vocabulary (top 50 only)

```python
import time

for entry in result[:50]:
    if entry['meaning'] is not None: continue
    try:
        r = requests.get('https://jisho.org/api/v1/search/words',
                         params={'keyword': entry['word']}, timeout=10)
        data = r.json().get('data', [])
        if data and data[0].get('senses'):
            entry['meaning'] = data[0]['senses'][0]['english_definitions'][0]
    except Exception:
        pass
    time.sleep(0.25)

with open('result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
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
        "meaning_mnemonic": "<radical>ear</radical> on a <radical>stool</radical>...",
        "reading_mnemonic": "...",
        "scene_hook": "An ear on a stool is how you TAKE notes by listening."
      }
    ]
  }
]
```

- Sorted by `frequency_in_section` descending within WK tier
- `kanji: []` never happens (kana-only words are excluded)
- `meaning: null` if neither WK vocab nor Jisho have an entry
- `reading_mnemonic: null` if kanji not in WaniKani
- `scene_hook: null` if mnemonic is absent or too short

## Dependencies

```
ebooklib  beautifulsoup4  lxml  janome  requests
```

## data/jp_top1000.txt

Must exist at `<BASE_DIR>/data/jp_top1000.txt`. Create empty if missing:
```bash
mkdir -p data && touch data/jp_top1000.txt
```
