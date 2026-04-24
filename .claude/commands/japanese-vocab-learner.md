---
name: japanese-vocab-learner
description: Build and maintain the WaniKani/Migaku Japanese vocabulary learner app. Use when asked to update index.html, add UI features, or rebuild from result.json. Covers data schema, self-contained HTML embedding, mnemonic rendering, and the WK radical→Unicode mapping.
---

# Japanese Vocabulary Learner — Session Knowledge

## How to build

The HTML is built by running `analyze_epub.py` (which calls `build_html.py`):
```bash
python analyze_epub.py <epub>
```

Or rebuild from an existing `result.json`:
```bash
python build_html.py result.json index.html
```

## Data schema (result.json produced by analyze_epub.py)

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
        "meaning_mnemonic": "There's an <radical>ear</radical> on a <radical>stool</radical>…"
      }
    ]
  }
]
```

Word-level keys: `word`, `reading`, `meaning` (may be `null`), `frequency_in_section`, `kanji[]`
Kanji-level keys: `character`, `meaning`, `reading`, `meaning_mnemonic`

**No `reading_mnemonic` field** — not stored (bloats data, not useful).
**No `scene_hook` field** — not stored (not displayed).

**Null handling:**
- `meaning: null` → display `—`
- `meaning_mnemonic: null` → show "No mnemonic available." in muted style

## UI Design Principles

### Reading AND meaning are inside the dropdown only
The collapsed card row shows: rank · word (JP) · kanji chips · freq · Learn button
**Reading is NOT shown in the collapsed row.** It appears only in the expanded card body.
**Meaning is NOT shown in the collapsed row.** It appears only in the expanded card body.
This forces the user to attempt recall before revealing reading and meaning.

### Card structure (collapsed)
```
[rank] [word-jp]       [chips] [freq] [Learn] [v]
```

### Card structure (expanded)
```
[word-jp large]   Reading: xxx
                  Meaning: yyy
                  Freq:    Nx in text

[Legend: ● Radical  ● Kanji  ● Vocabulary  ● Reading]

[大 kanji-glyph]  MEANING: take    READING: しゅ
  MEANING MNEMONIC
  Full mnemonic text with coloured tags...
```

No scene hook box. No reading mnemonic block.

### Fonts
```html
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;700;900&family=Inter:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
```
- UI text: `Inter`
- Japanese characters: `Noto Serif JP`

### Color scheme
```css
:root {
  --bg:       #f0ede8;   --surface:  #ffffff;    --raised:   #f8f7f5;
  --border:   rgba(0,0,0,0.09);   --border2:  rgba(0,0,0,0.16);
  --text:     #18160f;   --dim:      #6b6456;    --muted:    #aaa090;
  --accent:   #5a4fcf;   --accent-l: rgba(90,79,207,0.10);
  --wk-r:     #0093dd;   --wk-k:     #f0a000;
  --wk-v:     #9820c8;   --wk-rd:    #555;
  --green:    #1a9e6a;
}
```

### Kanji glyph — large, clean, no decoration
```css
.kanji-glyph {
  font-family: 'Noto Serif JP', serif;
  font-size: 3.8rem; font-weight: 900;
  color: var(--text);
  /* NO gradient, NO border, NO shadow */
}
```

## WaniKani Mnemonic Tags

Mnemonics contain custom HTML tags: `<radical>`, `<kanji>`, `<vocabulary>`, `<reading>`.
Parse with DOM (not regex) to avoid XSS:

```javascript
function renderMne(text) {
  if (!text) return '<em style="color:var(--muted)">No mnemonic available.</em>';
  const d = document.createElement('div');
  d.innerHTML = text;
  const wrap = (tag, cls) => {
    d.querySelectorAll(tag).forEach(el => {
      const s = document.createElement('span');
      s.className = cls;
      if (cls === 't-r') s.dataset.radical = el.textContent.trim().toLowerCase();
      s.textContent = el.textContent;
      el.replaceWith(s);
    });
  };
  wrap('radical','t-r'); wrap('kanji','t-k');
  wrap('vocabulary','t-v'); wrap('reading','t-rd');
  d.querySelectorAll(':not(span)').forEach(el => el.replaceWith(...el.childNodes));
  return d.innerHTML;
}
```

CSS classes and WaniKani colours:
```css
.t-r  { color: #0093dd; font-weight: 600; border-bottom: 1px dashed #0093dd; cursor: help; }
.t-k  { color: #f0a000; font-weight: 600; }
.t-v  { color: #9820c8; font-weight: 600; }
.t-rd { color: #555;    font-weight: 600; background: rgba(0,0,0,0.055);
        padding: 0 3px; border-radius: 3px; }
```

## Radical → Unicode Map (RC)

**CRITICAL: Do NOT hand-craft the RC map.** The correct source of truth is the
WaniKani `/v2/subjects?types=radical` API. Fetch it once and generate the full
map programmatically. The current `build_html.py` contains **485 entries** built
from the live WK API.

### How to regenerate RC if needed

```python
import requests, json, time

token = WK_TOKEN
headers = {'Authorization': f'Bearer {token}'}
radicals, url = [], 'https://api.wanikani.com/v2/subjects?types=radical&per_page=500'
while url:
    for attempt in range(5):
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 503: time.sleep(3*(attempt+1)); continue
        r.raise_for_status(); break
    d = r.json()
    radicals.extend(d['data'])
    url = d['pages'].get('next_url')
    time.sleep(0.3)

slug_to_char = {
    s['data']['slug'].replace('-',' ').lower(): s['data']['characters']
    for s in radicals if s['data'].get('characters')
}
# slug_to_char now has ~485 entries — embed as RC in build_html.py
```

### Key lookup rules

- `data-radical` on `.t-r` spans is set to `.toLowerCase()` — **all RC keys must be lowercase**.
- WK mnemonic text sometimes uses names that differ from the WK slug. Add aliases:
  ```javascript
  "horn":"角",        // WK slug: angle
  "hot peppers":"辛", // WK slug: spicy
  "one":"一",         // WK slug: ground
  "swords":"刃",      // WK slug: blade
  ```
- These aliases are already present at the bottom of the RC block in `build_html.py`.

### RDESC — truly image-only radicals

Only 10 WK radicals have no Unicode character at all (verified via API):

```javascript
const RDESC = {
  "beggar":      "WK custom — hunched figure with a bowl (image only)",
  "cactus":      "WK custom — spiky desert plant (image only)",
  "death star":  "WK custom — sphere with a trench (image only)",
  "explosion":   "WK custom — star-burst / kaboom shape (image only)",
  "hills":       "WK custom — two peaks side by side (image only)",
  "kick":        "WK custom — leg extending in a kick (image only)",
  "pope":        "WK custom — papal mitre / tall pointed hat (image only)",
  "rib cage":    "WK custom — curved protective bone cage (image only)",
  "satellite":   "WK custom — circular dish on a pole (image only)",
  "yurt":        "WK custom — round felt tent (image only)"
};
```

### Tooltip logic

```javascript
document.addEventListener('mouseover', e => {
  const t = e.target.closest('.t-r'); if (!t) return;
  const name = t.dataset.radical || '';
  const char = RC[name] ?? null;
  const desc = RDESC[name] ?? null;
  if (char) {
    ttCh.textContent = char; ttCh.className = 'tt-char'; ttDesc.textContent = '';
  } else {
    ttCh.textContent = '？'; ttCh.className = 'tt-char none';
    ttDesc.textContent = desc || 'WK custom radical (no Unicode equivalent)';
  }
  ttNm.textContent = name;
  moveTT(e); tt.classList.add('vis'); ttOn = true;
});
```

### Verifying coverage after changes

Run this before building to confirm zero missing radicals:

```python
import re, json
text = open('build_html.py', encoding='utf-8').read()
rc_keys = set(re.findall(r'"([^"]+)":', re.search(r'const RC = \{(.+?)\};', text, re.DOTALL).group(1)))
rd_keys = set(re.findall(r'"([^"]+)":', re.search(r'const RDESC = \{(.+?)\};', text, re.DOTALL).group(1)))
r = json.loads(open('result.json', encoding='utf-8').read())
used = {m.lower().strip()
        for e in r for k in e.get('kanji',[])
        for m in re.findall(r'<radical>([^<]+)</radical>', k.get('meaning_mnemonic','') or '')}
missing = used - (rc_keys | rd_keys)
print('Missing:', sorted(missing) or 'NONE')
```

## localStorage key
```javascript
let learned = new Set(JSON.parse(localStorage.getItem('kl-v3') || '[]'));
function save() { localStorage.setItem('kl-v3', JSON.stringify([...learned])); }
```

## Embedding data in self-contained HTML
```python
j = json.dumps(result, ensure_ascii=False, separators=(',',':'))
j = j.replace('</script>', r'<\/script>')   # prevent early script close
html = HTML_TEMPLATE.replace('const WORDS = [];', f'const WORDS = {j};')
```

## Common Pitfalls
- **`</script>` in JSON**: always escape before embedding
- **Reading shown in row**: do NOT show reading in collapsed row — only in expanded view
- **Meaning shown in row**: do NOT show meaning in collapsed row — only in expanded view
- **`meaning: null`**: render as `—`, never show "null"
- **`reading_mnemonic`**: do NOT add this field — removed from schema
- **`scene_hook`**: do NOT add this field — removed from schema
- **Radical `？`**: always show RDESC description too, never just `？` alone
- **Hand-crafting RC**: NEVER do this — always generate from WK API or use the existing 485-entry map in `build_html.py`
- **Capitalised RC keys**: all keys must be lowercase — the tooltip lookup uses `.toLowerCase()`
