#!/usr/bin/env python3
"""build_html.py — Embeds result.json data into the self-contained index.html."""

import json, re
from pathlib import Path

HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PLACEHOLDER_TITLE · Vocabulary</title>
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
    <span class="header-title">PLACEHOLDER_TITLE</span>
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
  "ability":"能","above":"上","accept":"受","again":"亦","alcohol":"酉",
  "alligator":"也","allocate":"充","angel":"ホ","angle":"角","animal":"犭",
  "announce":"告","anti":"反","arrow":"矢","asia":"亜","attach":"付",
  "axe":"斤","badger":"豸","bamboo":"竹","bar":"㦮","barb":"亅",
  "barracks":"屯","bathtub":"呂","beans":"豆","bear":"㠯","become":"成",
  "bed":"巴","before":"前","beforehand":"予","below":"下","belt":"帯",
  "big":"大","bird":"鳥","black":"黒","black hole":"复","blackjack":"龷",
  "blade":"刃","blame":"責","blood":"血","blue":"青","boat":"舟",
  "body":"身","boil":"灬","bone":"骨","book":"本","bookshelf":"冊",
  "boot":"堇","both":"両","bow":"弓","box":"凵","branch":"支",
  "bright":"明","broom":"帚","brush":"聿","buddy":"君","building":"阝",
  "bully":"鬲","bundle":"束","business":"業","cage":"匚","call":"召",
  "can":"缶","cane":"攵","canine":"戌","canopy":"广","cape":"𠃌","capital":"京",
  "car":"車","cat pirate":"卬","catapult":"呉","center":"央","ceremony":"弋",
  "certain":"必","change":"化","chapter":"章","charcoal":"尞","cheap":"安",
  "child":"子","chinese":"𦰩","circle":"丸","circumference":"周","city":"市",
  "clan":"氏","claw":"爪","cleat":"⺤","cliff":"厂","clothes":"衣",
  "cloud":"云","clown":"咅","coat rack":"疋","coffin":"耂","color":"色",
  "comfort":"楽","commander":"将","compare":"比","concave":"凹","conflict":"争",
  "construction":"工","control":"制","convex":"凸","coral":"丞","correct":"正",
  "cottage":"舎","courage":"勇","cow":"牛","crab":"其","crab trap":"甚",
  "criminal":"非","cross":"十","cyclops 133":"向","dance":"舛","dawn":"旦",
  "death":"亡","demon":"鬼","departure":"発","direction":"方","director":"司",
  "dirt":"土","district":"区","dog":"犬","dollar":"弗","door":"戸",
  "doubt":"疑","dragon":"竜","drawer":"母","droopy":"垂","drop":"丶",
  "drum":"壴","drunkard":"戈","dry":"干","dynamite":"丙","ear":"耳",
  "early":"早","east":"東","easy":"易","eat":"食","ego":"我",
  "elephant":"象","employ":"雇","energy":"气","enter":"入","escalator":"及",
  "eternity":"永","evening":"夕","every":"毎","excuse":"免","exit":"出",
  "eye":"目","face":"面","fang":"牙","farming":"農","fat":"太",
  "father":"父","fault":"失","favor":"恵","feathers":"羽","feeling":"感",
  "festival":"祭","few":"少","fingers":"扌","fins":"ハ","fire":"火",
  "fish":"魚","five":"五","flag":"尸","flood":"巛","flowers":"艹",
  "fly":"飛","foot":"足","football":"爰","forehead":"冖","form":"容",
  "former":"旧","fortune":"占","friend":"友","frostbite":"夌","fruit":"果",
  "fur":"毛","gambler":"尭","gate":"門","geoduck":"頁","giant":"巨",
  "gladiator":"龹","go":"行","gold":"金","good":"良","good luck":"吉",
  "grain":"禾","grass":"𭕄","greenhouse":"莫","grenade 386":"臼","ground":"一",
  "guard":"兑","guest":"客","gun":"𠂉","guy":"郎","hair":"彡",
  "half":"半","hand":"手","happiness":"幸","hat":"𠆢","have":"有",
  "head":"冂","heart":"心","heaven":"天","heavy":"重","height":"丈",
  "helicopter":"覀","hercules 316":"絜","hill":"岡","history":"史","hole":"穴",
  "hook":"ユ","horns":"丷","horse":"馬","hot pepper":"辟","house":"家",
  "humble":"申","hundred":"百","husband":"夫","ice":"冫","icicle":"丬",
  "idea":"意","imperial":"龍","insect":"虫","inside":"内","interval":"間",
  "jackhammer":"示","jammed in":"介","jet":"未","key":"乍","king":"王",
  "kiss":"各","knife":"刂","korea":"韋","lack":"欠","ladle":"斗",
  "landslide":"辰","lantern":"开","leader":"ｲ","leaf":"丆","leather":"革",
  "legs":"儿","library":"扁","lid":"亠","life":"生","lifeguard":"冓",
  "light":"光","line up":"並","lineage":"系","lion":"L","lip ring":"可",
  "loiter":"彳","long":"長","long ago":"昔","lovely":"麗","machine":"台",
  "mama":"マ","man":"男","mantis":"禹","mask":"曽","master":"主",
  "measurement":"寸","meat":"肉","meet":"会","melon":"瓜","member":"員",
  "middle":"中","mix":"交","mohawk":"啇","mole":"至","mona lisa":"兼",
  "moon":"月","morning":"𠦝","mountain":"山","mouth":"口","music":"曲",
  "mustache":"冋","mysterious":"玄","name":"名","narwhal":"ナ","nature":"然",
  "neck":"首","net":"罒","next":"次","night":"夜","nine":"九",
  "noon":"午","north":"北","nose":"乙","not":"不","nothing":"無",
  "now":"今","number":"番","nurse":"㐮","odd":"奇","old":"古",
  "older brother":"兄","omen":"兆","one sided":"片","oneself":"己","orders":"令",
  "origin":"元","original":"原","outfit":"衤","oversee":"監","paragraph":"句",
  "part":"分","past":"去","path":"辶","peace":"平","penguin":"敝","peoples":"民",
  "person":"人","pi":"兀","pig":"豕","pirate":"冘","plate":"皿",
  "plow":"耒","poem":"苟","pool":"勺","poop":"幺","power":"力",
  "prefecture":"県","preserve":"保","previous":"先","prison":"勹","private":"ム",
  "prize":"賞","proclaim":"宣","products":"品","protect":"守","public":"公",
  "ra 58":"ラ","rain":"雨","rake":"而","raptor cage 59":"久","reality":"真",
  "reason":"由","receive":"享","red":"赤","rejoice":"喜","renew":"更",
  "request":"求","restaurant":"亭","rice":"米","rice paddy":"田","right":"右",
  "righteousness":"義","river":"川","road":"道","rocket":"离","roof":"宀",
  "roof 225":"亼","root":"艮","run":"走","sake":"為","same":"同",
  "samurai":"士","saw":"巩","say":"言","scarecrow":"畐","scooter":"⻌",
  "scroll":"巻","see":"見","self":"自","sell":"売","servant":"臣",
  "seven":"七","sheep":"羊","shellfish":"貝","shop":"屋","showy":"華",
  "shrimp":"尺","shuriken":"彑","sick":"疒","sickle":"釆","signpost":"夆",
  "simple":"単","simultaneous":"斉","six 375":"六","skewer":"串","skin":"皮",
  "sky":"空","slice":"亥","slide":"丿","small":"小","snake":"巳",
  "someone":"者","soul":"忄","sound":"音","south":"南","spear":"矛",
  "specialty":"専","spicy":"辛","spider":"夋","spikes":"业","spirit":"ネ",
  "splinter":"禺","spoon":"匕","spring":"𡗗","squid":"㑒","stairs":"乃",
  "stamp":"卩","stand":"立","stick":"丨","stomach":"胃","stone":"石",
  "stool":"又","stop":"止","storehouse":"蔵","straight":"直","street":"丁",
  "substitute":"代","suit":"合","sun":"日","surplus":"余","sweet":"甘",
  "sword":"刀","syrup":"喿","table":"几","talent":"才","tall":"高",
  "task":"用","task 401":"務","teacher":"孝","temple":"寺","ten thousand":"万",
  "tent":"癶","think":"思","thousand":"千","thread":"糸","three":"三",
  "tiger":"虍","times":"回","toe":"ト","together":"共","tombstone":"圣",
  "tongue":"舌","tooth":"歯","top hat":"且","towel":"巾","trash":"𠫓",
  "treasure":"メ","treasure chest":"凶","tree":"木","triceratops":"⺌","tsunami":"氵",
  "turkey":"隹","turtle":"亀","turtle shell":"甲","twenty":"廾","two":"二",
  "umbrella":"乚","valley":"谷","valuable":"貴","viking":"龸","village":"里",
  "vines":"丩","violence":"暴","walk":"歩","warehouse":"倉","water":"水",
  "wave":"波","weapon":"殳","wedding":"甫","well":"井","west":"西",
  "wheat":"麦","white":"白","wide":"広","wife":"妻","wild":"荒",
  "wind":"風","window":"毋","wing":"勿","winter":"夂","wolverine":"ヨ",
  "woman":"女","womb":"坴","world":"世","wrap":"包","writing":"文",
  "yakuza":"歹","yellow":"黄","yoga":"廴","younger brother":"弟","zombie":"袁",
  // Mnemonic-name aliases (text in <radical> tags differs from WK slug)
  "horn":"角","hot peppers":"辛","one":"一","swords":"刃"
};

// Descriptions for custom WK radicals (no Unicode)
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


def build_html(result: list, out_path, title: str = '日本語'):
    out_path = Path(out_path)
    j = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
    j = j.replace('</script>', r'<\/script>')  # prevent early script close

    html = HTML_TEMPLATE.replace(
        'const WORDS = [];',
        f'const WORDS = {j};'
    ).replace('PLACEHOLDER_TITLE', title)

    out_path.write_text(html, encoding='utf-8')
    print(f'[ok] HTML written ({len(html)//1024} KB) → {out_path}')


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python build_html.py result.json [output.html] [title]')
        sys.exit(1)
    data  = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    out   = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('index.html')
    title = sys.argv[3] if len(sys.argv) > 3 else '日本語'
    build_html(data, out, title)
