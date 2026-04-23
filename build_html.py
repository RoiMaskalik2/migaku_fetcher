#!/usr/bin/env python3
"""build_html.py — Embeds result.json data into the self-contained index.html."""

import json, re
from pathlib import Path

HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>日本語 Vocabulary</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;700;900&family=Inter:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root {
  --bg:       #f0ede8;
  --surface:  #ffffff;
  --raised:   #f8f7f5;
  --border:   rgba(0,0,0,0.09);
  --border2:  rgba(0,0,0,0.16);
  --text:     #18160f;
  --dim:      #6b6456;
  --muted:    #aaa090;
  --accent:   #5a4fcf;
  --accent-l: rgba(90,79,207,0.10);
  --wk-r:     #0093dd;
  --wk-k:     #f0a000;
  --wk-v:     #9820c8;
  --wk-rd:    #555;
  --green:    #1a9e6a;
  --rr:       10px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}

/* ── Header ─────────────────────────────────────────────── */
.header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: 0 1px 6px rgba(0,0,0,0.07);
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.header-title {
  font-family: 'Noto Serif JP', serif;
  font-size: 1.25rem;
  font-weight: 900;
  letter-spacing: -0.01em;
}

.header-sub {
  font-size: 0.8rem;
  color: var(--dim);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-all, .filter-pending {
  padding: 5px 14px;
  border-radius: 20px;
  border: 1px solid var(--border2);
  background: transparent;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--dim);
  cursor: pointer;
  transition: all 0.15s;
}
.filter-all.active, .filter-pending.active,
.filter-all:hover, .filter-pending:hover {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.progress-text {
  font-size: 0.8rem;
  color: var(--dim);
  white-space: nowrap;
}

/* ── Word list ────────────────────────────────────────────── */
.list {
  max-width: 800px;
  margin: 18px auto;
  padding: 0 14px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

/* ── Card ─────────────────────────────────────────────────── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--rr);
  overflow: hidden;
  transition: box-shadow 0.15s;
}
.card:hover { box-shadow: 0 2px 14px rgba(0,0,0,0.07); }
.card.learned { opacity: 0.45; }
.card.hidden  { display: none; }

/* Collapsed row */
.card-row {
  display: grid;
  grid-template-columns: 32px 1fr auto;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
  gap: 10px;
  user-select: none;
  -webkit-user-select: none;
}
.card-row:hover { background: rgba(0,0,0,0.015); }

.rank {
  font-size: 0.72rem;
  color: var(--muted);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.row-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.word-jp {
  font-family: 'Noto Serif JP', serif;
  font-size: 1.55rem;
  font-weight: 700;
  line-height: 1;
  flex-shrink: 0;
  color: var(--text);
}

.row-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.kanji-chips {
  display: flex;
  gap: 3px;
}
.kanji-chip {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-l);
  font-family: 'Noto Serif JP', serif;
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--accent);
}

.freq {
  font-size: 0.72rem;
  color: var(--muted);
  background: var(--raised);
  padding: 3px 8px;
  border-radius: 10px;
  font-variant-numeric: tabular-nums;
}

.btn-learn {
  padding: 5px 13px;
  border-radius: 6px;
  border: none;
  background: var(--accent);
  color: #fff;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.btn-learn:hover { opacity: 0.82; }
.btn-learn.done  { background: var(--green); }

.chevron {
  color: var(--muted);
  transition: transform 0.2s;
  flex-shrink: 0;
}
.card.open .chevron { transform: rotate(180deg); }

/* ── Expanded body ────────────────────────────────────────── */
.card-body {
  display: none;
  padding: 0 18px 20px;
  border-top: 1px solid var(--border);
}
.card.open .card-body { display: block; }

/* Word header */
.word-header {
  display: flex;
  align-items: flex-end;
  gap: 18px;
  padding: 16px 0 14px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 16px;
}

.word-display {
  font-family: 'Noto Serif JP', serif;
  font-size: 3.4rem;
  font-weight: 900;
  line-height: 1;
  color: var(--text);
}

.word-meta {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding-bottom: 3px;
}

.meta-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.meta-label {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  font-weight: 600;
  width: 50px;
  flex-shrink: 0;
}

.meta-value {
  font-size: 0.95rem;
  color: var(--text);
}

.meta-value.reading {
  font-family: 'Noto Serif JP', serif;
  font-size: 1rem;
  color: var(--dim);
}

/* Kanji section */
.kanji-section {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.kanji-entry {
  display: flex;
  gap: 18px;
  padding: 16px 0;
  border-bottom: 1px solid var(--border);
}
.kanji-entry:last-child { border-bottom: none; }

.kanji-glyph {
  font-family: 'Noto Serif JP', serif;
  font-size: 3.8rem;
  font-weight: 900;
  line-height: 1;
  color: var(--text);
  width: 76px;
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 2px;
}

.kanji-info { flex: 1; min-width: 0; }

.kanji-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.kanji-meaning {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
}

.kanji-reading {
  font-family: 'Noto Serif JP', serif;
  font-size: 0.9rem;
  color: var(--dim);
}

/* Mnemonic blocks */
.mne-block { margin-top: 8px; }
.mne-block + .mne-block { margin-top: 12px; }

.mne-label {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  font-weight: 600;
  margin-bottom: 5px;
}

.mne-text {
  font-size: 0.88rem;
  line-height: 1.75;
  color: var(--text);
}

/* ── WaniKani tag colours ─────────────────────────────────── */
.t-r  { color: var(--wk-r); font-weight: 600; cursor: help;
        border-bottom: 1px dashed var(--wk-r); }
.t-k  { color: var(--wk-k); font-weight: 600; }
.t-v  { color: var(--wk-v); font-weight: 600; }
.t-rd { color: var(--wk-rd); font-weight: 600;
        background: rgba(0,0,0,0.055); padding: 0 3px; border-radius: 3px; }

/* ── Radical tooltip ─────────────────────────────────────── */
.tt {
  position: fixed;
  pointer-events: none;
  background: #1c1a14;
  color: #f0ede8;
  border-radius: 9px;
  padding: 9px 13px 8px;
  display: none;
  z-index: 999;
  text-align: center;
  min-width: 68px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.30);
}
.tt.vis { display: flex; flex-direction: column; align-items: center; }

.tt-char {
  font-family: 'Noto Serif JP', serif;
  font-size: 2rem;
  font-weight: 900;
  line-height: 1;
  color: var(--wk-r);
}
.tt-char.none { font-size: 0.85rem; color: #888; font-style: italic; }
.tt-name { font-size: 0.72rem; color: #bbb; margin-top: 2px; text-transform: lowercase; }
.tt-desc { font-size: 0.68rem; color: #888; margin-top: 1px; max-width: 110px; line-height: 1.3; }

/* ── Mnemonic legend ─────────────────────────────────────── */
.legend {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  padding: 10px 14px;
  background: var(--raised);
  border-radius: 7px;
  margin-bottom: 14px;
  font-size: 0.78rem;
}
.legend-item { display: flex; align-items: center; gap: 5px; color: var(--dim); }
.legend-dot  { width: 9px; height: 9px; border-radius: 50%; }
.ld-r  { background: var(--wk-r); }
.ld-k  { background: var(--wk-k); }
.ld-v  { background: var(--wk-v); }
.ld-rd { background: var(--wk-rd); }
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <span class="header-title">日本語</span>
    <span class="header-sub" id="hSub">loading...</span>
  </div>
  <div class="header-right">
    <button class="filter-all active" onclick="setFilter('all',this)">All</button>
    <button class="filter-pending" onclick="setFilter('pending',this)">To Learn</button>
    <span class="progress-text" id="progTxt"></span>
  </div>
</div>

<div class="list" id="list"></div>

<!-- Radical tooltip -->
<div class="tt" id="tt">
  <span class="tt-char" id="ttCh"></span>
  <span class="tt-name" id="ttNm"></span>
  <span class="tt-desc" id="ttDesc"></span>
</div>

<script>
const WORDS = [];

// ── Radical → Unicode map (extended) ──────────────────────
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
  "flower":"花","grass":"草","leaf":"葉","gold":"金","wind":"风",
  "snow":"雪","cloud":"雲","lightning":"雷","wave":"波",
  // Animals / creatures
  "bird":"鳥","fish":"魚","creature":"虫","beast":"獣","cow":"牛",
  "dog":"犬","horse":"馬","tiger":"虎","dragon":"龍","turtle":"亀",
  "turkey":"隹","snake":"蛇","whale":"鯨","shell":"貝",
  // Body
  "ear":"耳","eye":"目","mouth":"口","hand":"手","foot":"足",
  "heart":"心","bone":"骨","head":"首","body":"身","nose":"鼻",
  "tooth":"歯","hair":"毛","nail":"爪","finger":"指","arm":"腕",
  // People / family
  "person":"人","woman":"女","child":"子","man":"男","king":"王",
  "husband":"夫","father":"父","mother":"母","friend":"友",
  // Concepts
  "big":"大","small":"小","middle":"中","up":"上","down":"下",
  "inside":"内","outside":"外","before":"前","after":"後",
  "right":"右","left":"左","old":"古","new":"新",
  "high":"高","low":"低","long":"長","short":"短",
  "wide":"広","narrow":"狭","half":"半",
  // Directions
  "north":"北","south":"南","east":"東","west":"西",
  // Actions
  "walk":"歩","run":"走","go":"行","stop":"止","stand":"立",
  "sit":"座","die":"死","live":"生","say":"言","see":"見",
  "hear":"聞","write":"書","eat":"食","drink":"飲",
  "buy":"買","sell":"売","come":"来","exit":"出","enter":"入",
  // WK-specific with direct Unicode
  "stool":"又","loiter":"彳","scooter":"辶","fins":"八",
  "tsunami":"氵","temple":"寺","roof":"宀","master":"主",
  "thread":"糸","car":"車","door":"門","power":"力",
  "sword":"刀","bow":"弓","arrow":"矢","spring":"春",
  "music":"音","art":"工","self":"自","boat":"舟",
  "page":"頁","wing":"羽","dry":"干",
  "genius":"才","compare":"比","flowers":"艹","tombstone":"囗",
  "war":"戈","toe":"止","inch":"寸","direction":"方",
  "evening":"夕","winter":"冬","neck":"首",
  "private":"厶","hat2":"亼","bathtub":"呂",
  // Time / place
  "day":"日","night":"夜","morning":"朝","year":"年",
  "country":"国","town":"町","road":"道","house":"家",
  // Colors
  "white":"白","black":"黒","red":"赤","blue":"青","color":"色",
  // WK radical aliases with clear Unicode equivalents
  "again":"又","axe":"斤","book":"冊","canine":"犬",
  "construction":"工","demon":"鬼","dirt":"土","evenings":"夕",
  "gate":"門","grain":"禾","happiness":"幸","heavy":"重",
  "insect":"虫","knife":"刀","life":"生","mountains":"山",
  "not":"非","now":"今","oneself":"自","original":"元",
  "prison":"囚","rice paddy":"田","shellfish":"貝",
  "sick":"疒","sound":"音","village":"里","world":"世",
  "stamp":"印","treasure":"宝","fingers":"扌",
  "forehead":"額","sickle":"鎌","ability":"能",
  // Radicals that were previously missing — added after verifying Unicode
  "boil":"灬","circle":"丸","bamboo":"竹","blood":"血",
  "twenty":"廿","skin":"皮","hole":"穴","horn":"角",
  "pig":"豕","same":"同","dawn":"旦","clothes":"衣",
  "wrap":"勹","writing":"文","towel":"巾","kick":"足",
  "bright":"明","fortune":"吉","straight":"直",
  "hot peppers":"辛","swords":"刃","surplus":"余",
  "receive":"受","courage":"勇","ceremony":"礼",
  "Asia":"亜","ego":"我","cage":"囗",
  "circumference":"囲","clan":"族","both":"双",
  "interval":"間","street":"街","Chinese":"漢",
  "Imperial":"帝","face":"面","flag":"旗","guard":"守",
  "origin":"元","building":"戸","odd":"奇",
  "net":"罒","nothing":"無","pool":"沼","prize":"賞",
  "root":"根","certain":"必",
};

// Descriptions for custom WK radicals (no Unicode)
const RDESC = {
  // Original WK customs
  "gun":         "WK custom — looks like a sideways pistol (⌐■)",
  "explosion":   "WK custom — star-burst / kaboom shape",
  "wolverine":   "WK custom — claw / talon shape",
  "cactus":      "WK custom — spiky plant shape",
  "satellite":   "WK custom — circular dish on a pole",
  "coffin":      "WK custom — rectangular box with lid",
  "death star":  "WK custom — sphere with a trench",
  "gladiator":   "WK custom — armoured warrior",
  "pope":        "WK custom — papal mitre (tall pointed hat)",
  "lobster":     "WK custom — clawed sea creature",
  "squid":       "WK custom — tentacle creature",
  "hills":       "WK custom — two peaks side by side",
  "raptor":      "WK custom — small fast dinosaur",
  "scalpel":     "WK custom — small surgical blade",
  "cape":        "WK custom — flowing cloak shape",
  // Additional WK custom radicals
  "alligator":   "WK custom — long-snouted reptile",
  "animal":      "WK custom — general creature silhouette",
  "beggar":      "WK custom — hunched figure with a bowl",
  "black hole":  "WK custom — void / all-consuming darkness",
  "cleat":       "WK custom — T-shaped hook used for ropes",
  "drunkard":    "WK custom — stumbling off-balance figure",
  "easy":        "WK custom — simplified/breezy stroke pattern",
  "energy":      "WK custom — radiating force lines",
  "icicle":      "WK custom — frozen downward spike",
  "idea":        "WK custom — thought-bubble above head",
  "jammed in":   "WK custom — wedged / stuck-tight shape",
  "jet":         "WK custom — fast aircraft silhouette",
  "kiss":        "WK custom — two lips meeting",
  "korea":       "WK custom — Korean hanja symbol",
  "lantern":     "WK custom — hanging paper lantern",
  "leader":      "WK custom — figure at the front",
  "lifeguard":   "WK custom — rescue figure with float",
  "line up":     "WK custom — queue / row of people",
  "lion":        "WK custom — mane-and-face creature",
  "lip ring":    "WK custom — circular ornament on a mouth",
  "machine":     "WK custom — mechanical device with gears",
  "mama":        "WK custom — motherly / nurturing figure",
  "measurement": "WK custom — ruler / measuring-tool shape",
  "mix":         "WK custom — blended interlocking strokes",
  "mustache":    "WK custom — facial hair above upper lip",
  "narwhal":     "WK custom — spiral-horned whale",
  "nurse":       "WK custom — medical caregiver with cap",
  "omen":        "WK custom — foreboding sign / portent",
  "orders":      "WK custom — command issued from above",
  "outfit":      "WK custom — clothing / garment shape",
  "past":        "WK custom — time gone by (hourglass idea)",
  "poop":        "WK custom — waste pile (swirled mound)",
  "request":     "WK custom — petition / pleading gesture",
  "rib cage":    "WK custom — curved protective bone cage",
  "simple":      "WK custom — minimalist stroke arrangement",
  "soul":        "WK custom — ethereal spirit shape",
  "task":        "WK custom — duty / assigned work",
  "tent":        "WK custom — triangular peaked shelter",
  "together":    "WK custom — unified / joined shape",
  "viking":      "WK custom — Nordic warrior with horned helm",
  "weapon":      "WK custom — generic combat implement",
  "yakuza":      "WK custom — Japanese organised-crime figure",
  "good luck":   "WK custom — fortune / blessing symbol",
  "giant":       "WK custom — oversized imposing figure",
  "history":     "WK custom — recorded-past events scroll",
  "fruit":       "WK custom — rounded produce / hanging fruit",
  // Additional customs identified from live mnemonics
  "blackjack":   "WK custom — 21 / playing-card game shape",
  "coat rack":   "WK custom — T-bar hanger shape",
  "droopy":      "WK custom — hanging downward stroke",
  "drum":        "WK custom — cylindrical percussion instrument",
  "greenhouse":  "WK custom — glass structure for growing plants",
  "helicopter":  "WK custom — rotary-wing aircraft",
  "jackhammer":  "WK custom — pneumatic drill / piston shape",
  "landslide":   "WK custom — earth or rock falling downhill",
  "mohawk":      "WK custom — central-strip hairstyle",
  "bathtub":     "WK custom — rectangular soaking tub",
  "womb":        "WK custom — inner chamber / birth space",
  "oversee":     "WK custom — watching / supervising from above",
  "branch":      "WK custom — forking tree limb (if not 枝)",
  "certain":     "WK custom — definite / no-doubt mark",
  "clan":        "WK custom — family lineage group (if not 族)",
  "flag":        "WK custom — rectangular cloth on a pole (if not 旗)",
  "wrap":        "WK custom — enclosing fold (Unicode: 勹)",
  "trash":       "WK custom — discarded-waste pile",
  "towel":       "WK custom — hanging cloth strip (Unicode: 巾)",
  "yurt":        "WK custom — round felt tent (Mongolian dwelling)",
  "triceratops": "WK custom — three-horned dinosaur",
  "both":        "WK custom — pair / two things together (Unicode: 双)",
  "surplus":     "WK custom — leftover / excess (Unicode: 余)",
  "interval":    "WK custom — gap between things (Unicode: 間)",
};

// ── Mnemonic renderer ─────────────────────────────────────
function renderMne(text) {
  if (!text) return '<em style="color:var(--muted)">No mnemonic available.</em>';
  const d = document.createElement('div');
  d.innerHTML = text;
  const wrap = (tag, cls) =>
    d.querySelectorAll(tag).forEach(el => {
      const s = document.createElement('span');
      s.className = cls;
      if (cls === 't-r') s.dataset.radical = el.textContent.trim().toLowerCase();
      s.textContent = el.textContent;
      el.replaceWith(s);
    });
  wrap('radical','t-r'); wrap('kanji','t-k');
  wrap('vocabulary','t-v'); wrap('reading','t-rd');
  // Strip remaining unknown tags
  d.querySelectorAll(':not(span)').forEach(el => el.replaceWith(...el.childNodes));
  return d.innerHTML;
}

// ── Build card HTML ───────────────────────────────────────
function buildCard(w, i) {
  const kanji = w.kanji || [];
  const chips = kanji.map(k =>
    `<span class="kanji-chip">${k.character}</span>`
  ).join('');

  let kanjiHTML = '';
  if (kanji.length) {
    kanjiHTML = `
      <div class="legend">
        <div class="legend-item"><span class="legend-dot ld-r"></span>Radical</div>
        <div class="legend-item"><span class="legend-dot ld-k"></span>Kanji</div>
        <div class="legend-item"><span class="legend-dot ld-v"></span>Vocabulary</div>
        <div class="legend-item"><span class="legend-dot ld-rd"></span>Reading</div>
      </div>
      <div class="kanji-section">
    `;

    for (const k of kanji) {
      const mm = renderMne(k.meaning_mnemonic);

      kanjiHTML += `
        <div class="kanji-entry">
          <div class="kanji-glyph">${k.character}</div>
          <div class="kanji-info">
            <div class="kanji-head">
              <span class="kanji-meaning">${k.meaning ? escHtml(k.meaning) : '—'}</span>
              ${k.reading ? `<span class="kanji-reading">${escHtml(k.reading)}</span>` : ''}
            </div>
            <div class="mne-block">
              <div class="mne-label">Meaning mnemonic</div>
              <div class="mne-text">${mm}</div>
            </div>
          </div>
        </div>
      `;
    }
    kanjiHTML += '</div>';
  }

  return `
    <div class="card" id="c${i}" data-i="${i}">
      <div class="card-row" onclick="toggle(${i})">
        <span class="rank">${i+1}</span>
        <div class="row-main">
          <span class="word-jp">${w.word}</span>
        </div>
        <div class="row-right">
          <div class="kanji-chips">${chips}</div>
          <span class="freq">${w.frequency_in_section}×</span>
          <button class="btn-learn${learned.has(w.word)?` done`:''}"
                  onclick="toggleLearn(event,${i})">${learned.has(w.word)?'Learned':'Learn'}</button>
          <svg class="chevron" width="14" height="14" viewBox="0 0 24 24"
               fill="none" stroke="currentColor" stroke-width="2.5"
               stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </div>
      </div>
      <div class="card-body">
        <div class="word-header">
          <div class="word-display">${w.word}</div>
          <div class="word-meta">
            <div class="meta-row">
              <span class="meta-label">Reading</span>
              <span class="meta-value reading">${w.reading ? escHtml(w.reading) : '—'}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">Meaning</span>
              <span class="meta-value">${w.meaning ? escHtml(w.meaning) : '—'}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">Freq</span>
              <span class="meta-value">${w.frequency_in_section}× in text</span>
            </div>
          </div>
        </div>
        ${kanjiHTML}
      </div>
    </div>
  `;
}

// ── State ─────────────────────────────────────────────────
let learned  = new Set(JSON.parse(localStorage.getItem('kl-v3') || '[]'));
let curFilter = 'all';

function save() { localStorage.setItem('kl-v3', JSON.stringify([...learned])); }

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

function toggle(i) {
  const card = document.getElementById('c'+i);
  card.classList.toggle('open');
}

function toggleLearn(ev, i) {
  ev.stopPropagation();
  const w   = WORDS[i];
  const btn = ev.currentTarget;
  if (learned.has(w.word)) {
    learned.delete(w.word);
    btn.textContent = 'Learn'; btn.classList.remove('done');
    document.getElementById('c'+i).classList.remove('learned');
  } else {
    learned.add(w.word);
    btn.textContent = 'Learned'; btn.classList.add('done');
    document.getElementById('c'+i).classList.add('learned');
  }
  save();
  updateProgress();
  if (curFilter === 'pending') applyFilter();
}

function updateProgress() {
  const done  = WORDS.filter(w => learned.has(w.word)).length;
  const total = WORDS.length;
  document.getElementById('progTxt').textContent = `${done} / ${total} learned`;
}

function setFilter(f, btn) {
  curFilter = f;
  document.querySelectorAll('.filter-all,.filter-pending').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFilter();
}

function applyFilter() {
  WORDS.forEach((w, i) => {
    const card = document.getElementById('c'+i);
    if (curFilter === 'pending') {
      card.classList.toggle('hidden', learned.has(w.word));
    } else {
      card.classList.remove('hidden');
    }
  });
}

// ── Tooltip ───────────────────────────────────────────────
const tt    = document.getElementById('tt');
const ttCh  = document.getElementById('ttCh');
const ttNm  = document.getElementById('ttNm');
const ttDesc= document.getElementById('ttDesc');
let ttOn = false;

function moveTT(e) {
  const x = e.clientX, y = e.clientY;
  const w = tt.offsetWidth  || 90;
  const h = tt.offsetHeight || 80;
  const vw = window.innerWidth, vh = window.innerHeight;
  tt.style.left = Math.min(x + 14, vw - w - 6) + 'px';
  tt.style.top  = Math.max(y - h - 10, 6) + 'px';
}

document.addEventListener('mouseover', e => {
  const t = e.target.closest('.t-r'); if (!t) return;
  const name = t.dataset.radical || '';
  const char = RC[name] ?? null;
  const desc = RDESC[name] ?? null;

  if (char) {
    ttCh.textContent = char;
    ttCh.className   = 'tt-char';
    ttDesc.textContent = '';
  } else {
    ttCh.textContent = '？';
    ttCh.className   = 'tt-char none';
    ttDesc.textContent = desc || 'WK custom radical (no Unicode equivalent)';
  }
  ttNm.textContent = name;
  moveTT(e);
  tt.classList.add('vis');
  ttOn = true;
});

document.addEventListener('mousemove', e => {
  if (ttOn && e.target.closest('.t-r')) moveTT(e);
});

document.addEventListener('mouseout', e => {
  if (!e.target.closest('.t-r')) return;
  const rel = e.relatedTarget;
  if (rel && rel.closest('.t-r')) return;
  tt.classList.remove('vis');
  ttOn = false;
});

// ── Init ──────────────────────────────────────────────────
(function() {
  const list = document.getElementById('list');
  list.innerHTML = WORDS.map((w,i) => buildCard(w,i)).join('');

  const done  = WORDS.filter(w => learned.has(w.word)).length;
  WORDS.forEach((w,i) => {
    if (learned.has(w.word)) document.getElementById('c'+i).classList.add('learned');
  });

  document.getElementById('hSub').textContent = `${WORDS.length} words · sorted by frequency`;
  updateProgress();
})();
</script>
</body>
</html>'''


def build_html(result: list, out_path):
    out_path = Path(out_path)
    j = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
    j = j.replace('</script>', r'<\/script>')  # prevent early script close

    html = HTML_TEMPLATE.replace(
        'const WORDS = [];',
        f'const WORDS = {j};'
    )

    out_path.write_text(html, encoding='utf-8')
    print(f'[ok] index.html written ({len(html)//1024} KB) → {out_path}')


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python build_html.py result.json [output.html]')
        sys.exit(1)
    data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    out  = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('index.html')
    build_html(data, out)
