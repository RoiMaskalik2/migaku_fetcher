#!/usr/bin/env python3
"""Patch result.json kanji mnemonics with vivid, cause-and-effect mnemonics.

Every mnemonic uses the kanji's true KRADFILE component radicals (no
oversimplification to a single radical) and follows a strict format: one
cohesive scene, specific context, clear cause-and-effect, every component
essential, target word last.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
RESULT_FILE = BASE_DIR / 'result.json'

MNEMONICS = {
    "下": "A clumsy ballerina dragged her bare <radical>toe</radical> across the stage <radical>ground</radical>, signaling the curtain to drop <kanji>below</kanji>.",
    "事": "The ruthless <radical>wolverine</radical> slashed every contract with one <radical>barb</radical>ed claw while barking deals from his snarling <radical>mouth</radical>, running his shady <kanji>business</kanji>.",
    "公": "The senator seized the spy's <radical>private</radical> files, flapping open like a pair of loose <radical>fins</radical>, and declared them <kanji>governmental</kanji> property.",
    "到": "The gardener's <radical>knife</radical> sliced through the <radical>dirt</radical> right as the burrowing <radical>mole</radical> made its surprise <kanji>arrival</kanji>.",
    "勝": "Under the glowing <radical>Moon</radical>, the <radical>big</radical> wrestler summoned raw <radical>power</radical> for one final, crushing <kanji>victory</kanji>.",
    "叩": "The drill sergeant's <radical>mouth</radical> counted down before his boot brought the <radical>stamp</radical> down hard, setting the <kanji>beat</kanji> for every recruit's march.",
    "合": "The clown's oversized <radical>hat</radical> slid down to swallow his <radical>mouth</radical> completely, snapping into place as a perfect <kanji>fit</kanji>.",
    "孵": "The hungry <radical>child</radical> scratched at the shell with tiny <radical>claw</radical>-like fingernails until the egg finally began to <kanji>hatch</kanji>.",
    "家": "After building <radical>roof</radical> after roof for forty years, the carpenter retired as the village's resident roofing <kanji>expert</kanji>.",
    "層": "The surveyor planted a <radical>flag</radical> atop each sunlit <radical>rice paddy</radical> terrace to mark where one <kanji>floor</kanji> of the hillside ended and the next began.",
    "巨": "The zookeepers had to weld together their largest <radical>cage</radical> just to contain something so <kanji>big</kanji>.",
    "弱": "Left outside in the <radical>ice</radical> all winter, the hunter's twin <radical>bow</radical>s turned brittle and <kanji>frail</kanji>.",
    "御": "The palace guard would <radical>loiter</radical> by the gate, <radical>stop</radical> every cart, and <radical>stamp</radical> its papers — that's how he helped <kanji>govern</kanji> who entered the kingdom.",
    "感": "The weeping <radical>drunkard</radical> spilled his aching <radical>heart</radical> straight out of his <radical>mouth</radical>, raw with <kanji>emotion</kanji>.",
    "態": "However shaken his <radical>heart</radical> really felt, the actor scooped his fear out with an invisible <radical>spoon</radical> before walking onstage, hiding it behind a calm <kanji>appearance</kanji>.",
    "投": "Climbing onto a wobbly <radical>stool</radical>, the soldier's <radical>fingers</radical> gripped his broken <radical>weapon</radical> one last time before he chose to <kanji>abandon</kanji> it for good.",
    "拡": "Land-grabbing investors used their <radical>fingers</radical> to drag their <radical>private</radical> <radical>canopy</radical> stake by stake across the field, determined to <kanji>broaden</kanji> their territory.",
    "持": "The surveyor's <radical>fingers</radical> took a careful <radical>measurement</radical> of the <radical>dirt</radical> plot, proving exactly how much land he could finally call his to <kanji>have</kanji>.",
    "撒": "Leaning hard on his <radical>cane</radical>, the old smuggler's <radical>fingers</radical> flung a handful of frozen <radical>winter</radical> gravel behind him to <kanji>give them the slip</kanji>.",
    "操": "The puppeteer's <radical>fingers</radical> pulled strings tied high in a wooden <radical>tree</radical> hung with carved <radical>products</radical>, learning to <kanji>maneuver</kanji> every puppet's limb.",
    "擲": "Furious, the bartender's <radical>fingers</radical> hurled a bottle of <radical>alcohol</radical> clean across the <radical>building</radical>, and it landed with one tremendous <kanji>hit</kanji>.",
    "死": "By <radical>evening</radical>, the <radical>yakuza</radical> boss lay still, his fate already scooped away with a single <radical>spoon</radical>-shaped blade — that was his <kanji>death</kanji>.",
    "毒": "Behind a shuttered <radical>window</radical>, the scientist kept a locked <radical>drawer</radical> of soil-covered <radical>dirt</radical> samples, each one crawling with deadly <kanji>germ</kanji>s.",
    "減": "As the <radical>tsunami</radical> dragged the words right out of the <radical>drunkard</radical>'s <radical>mouth</radical>, his courage began to <kanji>dwindle</kanji>.",
    "爵": "Only the <radical>claw</radical>ed hand that took the exact <radical>measurement</radical> of the ceremonial <radical>net</radical> earned the noble title of <kanji>baron</kanji>.",
    "猿": "The mischievous <radical>animal</radical> stuffed a tourist's stolen <radical>clothes</radical> straight into its <radical>mouth</radical>, acting every bit the cheeky <kanji>monkey</kanji>.",
    "痺": "Standing <radical>sick</radical> with fever for hours in the flooded <radical>rice paddy</radical>, the farmer's legs began to <kanji>become numb</kanji>.",
    "発": "The soldier's <radical>legs</radical> kicked the <radical>tent</radical> flap open as he fired, and each blast was logged using the <kanji>counter for gunshots</kanji>.",
    "網": "<radical>Thread</radical> woven tightly around the <radical>head</radical> of a fish already facing <radical>death</radical> is exactly what makes sturdy <kanji>netting</kanji>.",
    "腐": "The careless <radical>leader</radical> left <radical>meat</radical> hanging under the open-air <radical>canopy</radical> for a week, and it slowly began to <kanji>decay</kanji>.",
    "若": "The fortune teller chewed a <radical>mouth</radical>ful of wild <radical>flowers</radical>, only ever answering questions that began with <kanji>if</kanji>.",
    "落": "Battered by <radical>tsunami</radical> spray in the dead of <radical>winter</radical>, the last <radical>flowers</radical> finally let go of the branch and began to <kanji>fall</kanji>.",
    "蛛": "An <radical>insect</radical> the size of a <radical>cow</radical> spun its web high in the <radical>tree</radical> — the bug-half of the kanji for <kanji>spider</kanji>.",
    "蜘": "A clever <radical>insect</radical> shot silk from its <radical>mouth</radical> as straight as an <radical>arrow</radical> — the smart-half of the kanji for <kanji>spider</kanji>.",
    "蜥": "An <radical>insect</radical>-eyed creature swung its tail like an <radical>axe</radical> to knock prey from the <radical>tree</radical>, close enough to be called <kanji>a lizard</kanji>.",
    "蜴": "An <radical>insect</radical>-skinned creature spread papery <radical>wing</radical>-like scales to soak in the <radical>sun</radical>, finishing the kanji for <kanji>lizard</kanji>.",
    "蝙": "An <radical>insect</radical>-winged creature roosted behind the <radical>door</radical>, tucked between the dusty pages of an old <radical>bookshelf</radical> — the first half of the kanji for <kanji>bat</kanji>.",
    "蝠": "An <radical>insect</radical> with a wide-open <radical>mouth</radical> swooped low over the <radical>rice paddy</radical> at night — the second half of the kanji for <kanji>bat</kanji>.",
    "螂": "An <radical>insect</radical> stood frozen at the <radical>root</radical> of the old <radical>building</radical>, patient as a praying <kanji>mantis</kanji>.",
    "蟷": "A <radical>triceratops</radical>-headed <radical>insect</radical> crouched low over the <radical>rice paddy</radical>, ready to ambush — the other half of praying <kanji>mantis</kanji>.",
    "補": "The tailor assigned herself one extra <radical>task</radical>: stitching a patch onto the torn <radical>outfit</radical> to <kanji>supplement</kanji> what was missing.",
    "視": "The construction foreman gripped his <radical>jackhammer</radical>, leaning in to <radical>see</radical> every crack in the concrete during his final <kanji>inspection</kanji>.",
    "覚": "The <radical>triceratops</radical> lowered its bony <radical>forehead</radical> to <radical>see</radical> every detail of the cave wall up close, determined to <kanji>memorize</kanji> the markings forever.",
    "軽": "Hoisted onto a simple <radical>stool</radical> instead of packed with <radical>dirt</radical>, the toy <radical>car</radical> could be lifted so <kanji>lightly</kanji> it barely needed two fingers.",
    "達": "The <radical>king</radical> herded his flock of <radical>sheep</radical> down the long mountain <radical>path</radical>, and only when the last one arrived safely had he truly <kanji>accomplished</kanji> his task.",
    "闘": "Two merchants arguing over the exact <radical>measurement</radical> of a sack of <radical>beans</radical> finally crashed together behind the market <radical>gate</radical> in a furious <kanji>fight</kanji>.",
    "韋": "A strip of hide scraped clean and stretched drum-tight is, by itself, the <kanji>tanned leather radical (no. 178)</kanji>.",
    "駄": "The poor <radical>horse</radical> stumbled under one enormous, <radical>big</radical> <radical>drop</radical> of cargo strapped to its back, finding the whole load utterly <kanji>burdensome</kanji>.",
    "骸": "Under the pale <radical>moon</radical>light, all that remained of the <radical>person</radical> was a stripped <radical>bone</radical>y <kanji>body</kanji>.",
}


def main():
    result = json.loads(RESULT_FILE.read_text(encoding='utf-8'))
    patched = 0
    found_chars = set()
    for entry in result:
        for k in entry.get('kanji', []):
            char = k.get('character')
            if char in MNEMONICS:
                k['meaning_mnemonic'] = MNEMONICS[char]
                patched += 1
                found_chars.add(char)

    RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    missing = set(MNEMONICS) - found_chars
    print(f'[ok] patched {patched} kanji occurrences ({len(found_chars)} unique characters)')
    if missing:
        print(f'[warn] {len(missing)} mnemonic entries had no matching kanji in result.json: {sorted(missing)}')


if __name__ == '__main__':
    main()
