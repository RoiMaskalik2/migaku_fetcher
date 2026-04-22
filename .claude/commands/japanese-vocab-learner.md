---
name: japanese-vocab-learner
description: Build and maintain the WaniKani/Migaku Japanese vocabulary learner app. Use when asked to update index.html, add UI features, or rebuild from result.json. Covers data schema, self-contained HTML embedding, mnemonic rendering, extended radical→Unicode mapping, and reading-in-dropdown UI pattern.
---

# Japanese Vocabulary Learner — Session Knowledge

## How to build

The HTML is built by running `analyze_epub.py` (which calls `build_html.py`):
```bash
python analyze_epub.py <epub> <wk_token>
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

## Radical → Unicode Tooltip (extended map)

Radical tooltips fire on `.t-r` hover. For radicals not in the RC map,
show a helpful description from `RDESC` rather than just `？`.

```javascript
const RC = {
  // Numbers / basic
  "one":"一","two":"二","three":"三","four":"四","five":"五",
  "six":"六","seven":"七","eight":"八","nine":"九","ten":"十",
  "hundred":"百","thousand":"千","ten-thousand":"万",
  // Strokes
  "stick":"丨","drop":"丶","slide":"乚","horns":"丷","legs":"儿",
  "barb":"亅","cross":"十","hat":"亠","lid":"亡",
  "table":"几","jail":"冂","ice":"冫","canopy":"冖",
  "umbrella":"勹","cliff":"厂","spoon":"匕","seal":"卩",
  // Nature
  "sun":"日","moon":"月","fire":"火","water":"水","rain":"雨",
  "mountain":"山","river":"川","tree":"木","field":"田",
  "earth":"土","ground":"土","stone":"石","rice":"米",
  "flower":"花","grass":"草","leaf":"葉","gold":"金",
  "snow":"雪","cloud":"雲","lightning":"雷","wave":"波",
  // Animals
  "bird":"鳥","fish":"魚","creature":"虫","beast":"獣","cow":"牛",
  "dog":"犬","horse":"馬","tiger":"虎","dragon":"龍","turtle":"亀",
  "turkey":"隹","shell":"貝",
  // Body
  "ear":"耳","eye":"目","mouth":"口","hand":"手","foot":"足",
  "heart":"心","bone":"骨","head":"首","body":"身","nose":"鼻",
  "nail":"爪","hair":"毛",
  // People
  "person":"人","woman":"女","child":"子","man":"男","king":"王",
  "husband":"夫","father":"父","mother":"母","friend":"友",
  // Concepts
  "big":"大","small":"小","middle":"中","up":"上","down":"下",
  "inside":"内","outside":"外","before":"前","after":"後",
  "right":"右","left":"左","old":"古","new":"新",
  "high":"高","low":"低","long":"長","short":"短","half":"半",
  "north":"北","south":"南","east":"東","west":"西",
  // Actions
  "walk":"歩","run":"走","go":"行","stop":"止","stand":"立",
  "die":"死","live":"生","say":"言","see":"見","hear":"聞",
  "write":"書","eat":"食","drink":"飲","buy":"買","sell":"売",
  "come":"来","exit":"出","enter":"入",
  // WK-named radicals with Unicode
  "stool":"又","loiter":"彳","scooter":"辶","fins":"八",
  "tsunami":"氵","temple":"寺","roof":"宀","master":"主",
  "thread":"糸","car":"車","door":"門","power":"力",
  "sword":"刀","bow":"弓","arrow":"矢","spring":"春",
  "music":"音","art":"工","self":"自","boat":"舟",
  "page":"頁","wing":"羽","dry":"干","genius":"才",
  "compare":"比","flowers":"艹","tombstone":"囗",
  "war":"戈","toe":"止","inch":"寸","direction":"方",
  "evening":"夕","winter":"冬","neck":"首","private":"厶",
};

// For WK custom radicals (no Unicode), show a description
const RDESC = {
  "gun":         "WK custom — looks like a sideways pistol (⌐■)",
  "explosion":   "WK custom — star-burst / kaboom shape",
  "wolverine":   "WK custom — claw / talon shape",
  "cactus":      "WK custom — spiky plant shape",
  "satellite":   "WK custom — circular dish on a pole",
  "coffin":      "WK custom — rectangular box with lid",
  "death star":  "WK custom — sphere with a trench",
  "gladiator":   "WK custom — armoured warrior shape",
  "pope":        "WK custom — tall pointed mitre hat",
  "lobster":     "WK custom — clawed sea creature",
  "hills":       "WK custom — two peaks side by side",
};
```

Tooltip logic:
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
