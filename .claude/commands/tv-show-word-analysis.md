---
name: tv-show-word-analysis
description: Analyze SRT subtitle files from a Japanese TV show to find the top 100 high-frequency unknown vocabulary with WaniKani kanji mnemonics. No Migaku login required — start directly from the SRT files. Use when the user wants to study vocabulary from a Japanese TV show or anime.
---

# Japanese TV Show Word Frequency Analyzer

Given one or more Japanese `.srt` subtitle files, produce a ranked JSON list of
the **top 100** unknown words (kanji must be in WaniKani) with frequency, reading,
and WaniKani kanji meaning mnemonics.

No Migaku credentials needed — filtering uses `migaku_data/known_words.json` if
it already exists, otherwise falls back to `data/jp_top1000.txt` alone.

## Prerequisites

Ask the user for:
- **SRT file paths** — one or more `.srt` files (whole season = all episodes)
- **WaniKani API token** — required for kanji/vocabulary lookup
- **`BASE_DIR`** — absolute path to the project directory

Optionally, if the user already ran `migaku_fetch.py` before, `known_words.json`
will be used automatically for better filtering.

## Token Efficiency Rules (follow strictly)
- **Never** fetch all WaniKani subjects. Use the `slugs` parameter with only kanji in the final word list.
- Filter to **freq >= 2 AND has kanji** before the WaniKani call.
- **Two WaniKani API calls**: one for kanji, one for vocabulary (meanings).
- Use the tokenisation cache (`data/srt_counts_<hash>.json`) — skip re-tokenising if it exists.
- Do NOT echo `result.json` back to the user — it is too large. Report stats only.
- **result.json schema is lean**: only store `character`, `meaning`, `reading`, `meaning_mnemonic` per kanji.

---

## Workflow

Run `analyze_srt.py` which handles all steps:
```bash
cd <BASE_DIR>
python analyze_srt.py <SRT_PATH_1> [<SRT_PATH_2> ...] --wk-token <WK_TOKEN>
```

To analyse a full season, pass all episode SRT files:
```bash
python analyze_srt.py subs/ep01.srt subs/ep02.srt subs/ep03.srt --wk-token <WK_TOKEN>
```

The script does the following internally:

### 1. Find the data

Locate in `<BASE_DIR>`:
- The `.srt` file(s) to analyze
- `migaku_data/known_words.json` — used if present (output from `migaku-fetch` skill)
- `data/jp_top1000.txt` — always loaded as secondary baseline
- `data/srt_counts_<hash>.json` — tokenisation cache (auto-created on first run)

### 2. Parse SRT files → clean Japanese text

Strip sequence numbers, timestamps, and HTML tags from each SRT file.
Concatenate dialogue from all files into a single text blob.

```python
import re

def parse_srt(path: Path) -> str:
    text = path.read_text(encoding='utf-8', errors='replace')
    # Remove sequence numbers (lone integers on their own line)
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    # Remove timestamp lines (00:00:00,000 --> 00:00:00,000)
    text = re.sub(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}', '', text)
    # Remove HTML/ASS tags (<i>, {\an8}, etc.)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\{[^}]+\}', '', text)
    return text

all_text = '\n'.join(parse_srt(Path(p)) for p in srt_paths)
```

### 3. Cache key from combined SRT content

```python
import hashlib
cache_key = hashlib.md5(all_text.encode('utf-8')).hexdigest()[:8]
cache_file = DATA_DIR / f'srt_counts_{cache_key}.json'
```

### 4. Tokenise with janome (cached by content hash)

Same tokeniser as `analyze_epub.py` — compound noun buffering included.

```python
from janome.tokenizer import Tokenizer
from collections import Counter

if cache_file.exists():
    cached = json.loads(cache_file.read_text(encoding='utf-8'))
    word_count = Counter(cached['counts'])
    word_reading = {w: kata_to_hira(r) for w, r in cached['readings'].items()}
else:
    KEEP_POS = {'名詞', '動詞', '形容詞', '副詞'}
    NOUN_COMPOUND_TYPES = {'一般', 'サ変接続', '固有名詞', '副詞可能', '数', 'ナイ形容詞語幹'}
    tokenizer = Tokenizer()
    word_count = Counter()
    word_reading = {}
    # ... same compound-noun buffering logic as analyze_epub.py ...
    cache_file.write_text(
        json.dumps({'counts': dict(word_count), 'readings': word_reading},
                   ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
```

### 5. Filter against known words

```python
known = set()
known_file = MIGAKU_DATA / 'known_words.json'
if known_file.exists():
    raw = json.loads(known_file.read_text(encoding='utf-8'))
    known = {item['dictForm'] if isinstance(item, dict) else item for item in raw}
    known.discard('')
    print(f'[ok] {len(known)} known words from Migaku SRS')
else:
    print('[info] no known_words.json — filtering by jp_top1000.txt only')

common = set()
top1k_file = DATA_DIR / 'jp_top1000.txt'
if top1k_file.exists():
    common = {l.strip() for l in top1k_file.read_text(encoding='utf-8').splitlines() if l.strip()}

candidates = [
    (w, cnt) for w, cnt in word_count.most_common()
    if w not in known and w not in common and cnt >= MIN_FREQ and has_kanji(w)
]
```

### 6. Fetch WaniKani kanji data (single targeted call)

```python
all_kanji = sorted({c for w, _ in candidates for c in w if is_kanji(c)})
resp = requests.get(
    'https://api.wanikani.com/v2/subjects',
    params={'types': 'kanji', 'slugs': ','.join(all_kanji)},
    headers={'Authorization': f'Bearer {wk_token}'},
    timeout=30
)
resp.raise_for_status()
wk_kanji = {s['data']['characters']: s['data'] for s in resp.json()['data']}
```

### 6.5. WK-focused ranking — prefer words where ALL kanji are in WaniKani

```python
TOP_N = 100

tier1, tier2 = [], []
for w, cnt in candidates:
    chars = [c for c in w if is_kanji(c)]
    in_wk = sum(1 for c in chars if c in wk_kanji)
    if in_wk == len(chars):
        tier1.append((w, cnt))   # all kanji in WK — preferred
    elif in_wk > 0:
        tier2.append((w, cnt))   # some kanji in WK

final_words = (tier1 + tier2)[:TOP_N]
```

### 7. Fetch WaniKani vocabulary meanings (second targeted call)

```python
word_slugs = ','.join(w for w, _ in final_words)
resp_vocab = requests.get(
    'https://api.wanikani.com/v2/subjects',
    params={'types': 'vocabulary', 'slugs': word_slugs},
    headers={'Authorization': f'Bearer {wk_token}'},
    timeout=30
)
wk_vocab = {s['data']['characters']: s['data'] for s in resp_vocab.json()['data']}
```

### 8. Build result.json — lean schema

```python
result = []
for word, freq in final_words:
    wv = wk_vocab.get(word, {})
    meaning = next((m['meaning'] for m in wv.get('meanings', []) if m.get('primary')), None)

    kanji_list = []
    for c in word:
        if not is_kanji(c): continue
        d = wk_kanji.get(c, {})
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
```

### 8.5. Jisho fallback for words not in WK vocabulary (all missing meanings)

```python
for entry in result:
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
```

### 9. Save result.json and generate index.html

```python
out = BASE_DIR / 'result.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

from build_html import build_html
build_html(result, BASE_DIR / 'index.html')
```

### 10. Report stats only — do NOT echo result.json

```
SRT files parsed:          <N files, total chars>
Words tokenised:           <total tokens>
Unknown kanji-words:       <N candidates>
WK-focused (top 100):      <N final>
With meanings:             <N>
Top 5: <word> (<freq>x), ...
index.html ready — open in browser to study.
```

---

## Output schema (result.json)

Same schema as `epub-word-analysis`:

```json
[
  {
    "word": "警察",
    "reading": "けいさつ",
    "meaning": "police",
    "frequency_in_section": 37,
    "kanji": [
      {
        "character": "警",
        "meaning": "warn",
        "reading": "けい",
        "meaning_mnemonic": "<radical>salute</radical> with a <radical>mouth</radical>..."
      }
    ]
  }
]
```

- Sorted by `frequency_in_section` descending within WK tier
- `kanji: []` never happens (kana-only words are excluded)
- `meaning: null` if neither WK vocab nor Jisho have an entry
- `frequency_in_section` reflects total count across **all** provided SRT files

## Encoding notes

SRT files from different sources may use UTF-8, UTF-8-BOM, or Shift-JIS.
Always open with `errors='replace'` and detect BOM:
```python
text = path.read_bytes()
if text.startswith(b'\xef\xbb\xbf'):
    text = text[3:]  # strip UTF-8 BOM
text = text.decode('utf-8', errors='replace')
```

## Dependencies

```
janome  requests
```

(`ebooklib`, `beautifulsoup4`, `lxml` are **not** needed for SRT analysis.)
