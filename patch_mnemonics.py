#!/usr/bin/env python3
"""Patch result.json kanji mnemonics with accurate KRADFILE-based multi-radical text."""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
RESULT_FILE = BASE_DIR / 'result.json'

MNEMONICS = {
    "下": "A <radical>toe</radical> hangs down past the <radical>ground</radical> line — whatever's hanging stays <kanji>below</kanji>.",
    "事": "A <radical>wolverine</radical> with a <radical>barb</radical>ed claw runs its <radical>mouth</radical> about all its daily <kanji>business</kanji>.",
    "公": "Splitting your <radical>private</radical> matters open like a pair of <radical>fins</radical> for everyone to see makes them <kanji>public</kanji>.",
    "到": "A <radical>knife</radical> marks the spot in the <radical>dirt</radical> where the <radical>mole</radical> finally makes its <kanji>arrival</kanji>.",
    "勝": "<radical>Moon</radical>light shining on a <radical>big</radical>, <radical>power</radical>ful fist is how legends always <kanji>win</kanji>.",
    "叩": "A <radical>mouth</radical> shouting next to a <radical>stamp</radical>ing fist is how you <kanji>beat</kanji> a drum in time with your yelling.",
    "合": "Putting a <radical>hat</radical> over a <radical>mouth</radical> so the two finally <kanji>fit</kanji> together just right.",
    "孵": "A <radical>child</radical>'s <radical>claw</radical>s stamp their way out through the shell — that's how an egg <kanji>hatch</kanji>es.",
    "家": "A pig living under a <radical>roof</radical> is simply what every <kanji>house</kanji> looks like to this kanji.",
    "層": "A <radical>flag</radical> planted over a sunlit <radical>rice paddy</radical>, one level after another, marks each <kanji>floor</kanji> of the tower.",
    "巨": "A <radical>cage</radical> built too small can never hold a <kanji>giant</kanji>.",
    "弱": "Two <radical>bow</radical>s left out in the <radical>ice</radical>, drooping and brittle, can only ever be <kanji>weak</kanji>.",
    "御": "<radical>Loiter</radical>ing beside royalty, you <radical>stop</radical> and <radical>stamp</radical> your approval to <kanji>govern</kanji> the road they travel.",
    "感": "Your <radical>mouth</radical>, your <radical>heart</radical>, even your inner <radical>drunkard</radical> — every part of you reacts to a strong <kanji>feeling</kanji>.",
    "態": "However your <radical>heart</radical> secretly feels, scooped out with a <radical>spoon</radical> for all to see, is your current <kanji>condition</kanji>.",
    "投": "Your <radical>fingers</radical> grip a <radical>weapon</radical> and let it fly off the <radical>stool</radical> — that's how you <kanji>throw</kanji> it.",
    "拡": "Your <radical>fingers</radical> stretch a <radical>private</radical> <radical>canopy</radical> wider and wider to <kanji>broaden</kanji> the shade.",
    "持": "Your <radical>fingers</radical> take a <radical>measurement</radical> of the <radical>dirt</radical> you now <kanji>have</kanji>.",
    "撒": "<radical>Fingers</radical> swinging a <radical>cane</radical> through the <radical>winter</radical> wind <kanji>scatter</kanji> seeds across the frozen field.",
    "操": "<radical>Fingers</radical> pulling strings tied to a <radical>tree</radical> full of little wooden <radical>products</radical> is exactly how you <kanji>manipulate</kanji> a puppet.",
    "擲": "<radical>Fingers</radical> hurl an empty <radical>alcohol</radical> bottle clean over the <radical>building</radical> — that's how you <kanji>fling</kanji> something.",
    "死": "By <radical>evening</radical>, the <radical>yakuza</radical> had already scooped out his fate with a <radical>spoon</radical> — that's <kanji>death</kanji>.",
    "毒": "What grows from the <radical>dirt</radical> in a locked <radical>drawer</radical> behind a shuttered <radical>window</radical> is pure <kanji>poison</kanji>.",
    "減": "A <radical>tsunami</radical> drags the <radical>drunkard</radical>'s words right out of his <radical>mouth</radical> — there's a steady <kanji>decrease</kanji> in everything he has left.",
    "爵": "A <radical>claw</radical>ed hand takes the exact <radical>measurement</radical> of a ceremonial <radical>net</radical> — only a <kanji>baron</kanji> earns the right to wear it.",
    "猿": "An <radical>animal</radical> wearing stolen <radical>clothes</radical> with dirt all over its <radical>mouth</radical> is, of course, a cheeky little <kanji>monkey</kanji>.",
    "痺": "<radical>Sick</radical>ness spreading through a <radical>rice paddy</radical>'s worth of nerves until you can't feel a thing — that creeping <kanji>numbness</kanji>.",
    "発": "<radical>Legs</radical> kicking off the ground from under a <radical>tent</radical> flap is how you <kanji>emit</kanji> a sudden burst of energy.",
    "網": "<radical>Thread</radical> woven around the <radical>head</radical> of something already facing <radical>death</radical> is exactly what catches it in a <kanji>net</kanji>.",
    "腐": "A <radical>leader</radical> leaves <radical>meat</radical> out under the <radical>canopy</radical> for too long, and it starts to <kanji>decay</kanji>.",
    "若": "<radical>Flowers</radical> still finding the shape of their own <radical>mouth</radical> — that's how plants look when they're <kanji>young</kanji>.",
    "落": "<radical>Flowers</radical> dripping with <radical>tsunami</radical> water in the dead of <radical>winter</radical>, letting go of the branch one by one — that's how petals <kanji>fall</kanji>.",
    "蛛": "An <radical>insect</radical> climbing up a <radical>cow</radical> standing next to a <radical>tree</radical> is the bug-half of the kanji for <kanji>spider</kanji>.",
    "蜘": "An <radical>insect</radical> that shoots answers from its <radical>mouth</radical> like an <radical>arrow</radical> is the clever-half of the kanji for <kanji>spider</kanji>.",
    "蜥": "An <radical>insect</radical> swinging an <radical>axe</radical> at a <radical>tree</radical> is, in this kanji's eyes, close enough to a <kanji>lizard</kanji>.",
    "蜴": "An <radical>insect</radical> with <radical>wing</radical>-like skin, changing colors in the <radical>sun</radical>, is the second half of <kanji>lizard</kanji>.",
    "蝙": "An <radical>insect</radical> roosting behind a <radical>door</radical>, tucked between the pages of an old <radical>bookshelf</radical>, is the first half of the kanji for <kanji>bat</kanji>.",
    "蝠": "An <radical>insect</radical> with a wide-open <radical>mouth</radical>, swooping low over a <radical>rice paddy</radical> at night, is the second half of the kanji for <kanji>bat</kanji>.",
    "螂": "An <radical>insect</radical> standing guard at the <radical>root</radical> of a <radical>building</radical> is half of the word for praying <kanji>mantis</kanji>.",
    "蟷": "An <radical>insect</radical> with a <radical>triceratops</radical>-like head, lurking low over a <radical>rice paddy</radical>, ready to ambush anything that moves, is the other half of praying <kanji>mantis</kanji>.",
    "補": "Sewing an extra <radical>task</radical> onto your <radical>outfit</radical> is the simplest way to <kanji>supplement</kanji> what's missing.",
    "視": "Standing before a sacred <radical>jackhammer</radical>-altar, you finally <radical>see</radical> clearly enough for a proper <kanji>inspection</kanji>.",
    "覚": "A <radical>triceratops</radical> uses its bony <radical>forehead</radical> and sharp eyes to <radical>see</radical> and <kanji>perceive</kanji> everything around it.",
    "軽": "A <radical>car</radical> sitting on a <radical>stool</radical> instead of a pile of <radical>dirt</radical> is so much easier to lift — that's why it feels <kanji>light</kanji>.",
    "達": "A <radical>king</radical> herding <radical>sheep</radical> down a long <radical>path</radical> will eventually <kanji>reach</kanji> the goal, however long it takes.",
    "闘": "Two warriors arguing over the exact <radical>measurement</radical> of a pot of <radical>beans</radical>, crashing together behind the <radical>gate</radical>, refuse to back down from the <kanji>fight</kanji>.",
    "韋": "A length of hide, scraped clean and stretched tight, is simply the radical and kanji for tanned <kanji>leather</kanji> itself.",
    "駄": "A <radical>horse</radical> loaded down with one <radical>big</radical>, awkward <radical>drop</radical> of cargo finds the whole trip <kanji>burdensome</kanji>.",
    "骸": "What's left of a <radical>person</radical>'s <radical>bone</radical>y body under the pale <radical>moon</radical>light, long after everything else has rotted away, is the <kanji>remains</kanji>.",
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
