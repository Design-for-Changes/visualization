#!/usr/bin/env python3
"""Add romanized slug (name_en) to diet_members_socials_enriched.json."""
import json
import re
from pathlib import Path
from unicodedata import normalize

INPUT = Path("data/diet_members_socials_enriched.json")
OUTPUT = INPUT  # in-place overwrite

HIRAGANA_MAP = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "ゐ": "wi", "ゑ": "we", "を": "o",
    "ん": "n",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ゔ": "vu",
    "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o",
    "ゃ": "ya", "ゅ": "yu", "ょ": "yo",
}

DIGRAPH_MAP = {
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo",
    "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
    "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
    "じゃ": "ja", "じゅ": "ju", "じょ": "jo",
    "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
    "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
    "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo",
    "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
    "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",
    "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
    "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo",
    "う゛ぁ": "va", "う゛ぃ": "vi", "う゛ぇ": "ve", "う゛ぉ": "vo",
}

SMALL_TSU = {"っ", "ッ"}
PROLONG = "ー"


def katakana_to_hiragana(text: str) -> str:
    result = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F3:
            result.append(chr(code - 0x60))
        else:
            result.append(ch)
    return "".join(result)


def kana_token_to_romaji(token: str) -> str:
    token = katakana_to_hiragana(token)
    chars = list(token)
    result = []
    i = 0
    while i < len(chars):
        ch = chars[i]
        if ch in SMALL_TSU:
            # double the consonant of the next character
            if i + 1 < len(chars):
                next_ch = chars[i + 1]
                pair = next_ch
                if i + 2 < len(chars):
                    combo = next_ch + chars[i + 2]
                    if combo in DIGRAPH_MAP:
                        pair = combo
                roma = (DIGRAPH_MAP.get(pair) or HIRAGANA_MAP.get(next_ch) or "")
                if roma:
                    result.append(roma[0])
            i += 1
            continue
        if ch == PROLONG:
            if result:
                last_vowel = re.search(r"[aeiou]", result[-1][::-1])
                if last_vowel:
                    result.append(last_vowel.group(0))
            i += 1
            continue
        pair = None
        if i + 1 < len(chars):
            combo = ch + chars[i + 1]
            if combo in DIGRAPH_MAP:
                pair = combo
        if pair:
            result.append(DIGRAPH_MAP[pair])
            i += 2
            continue
        roma = HIRAGANA_MAP.get(ch)
        if roma:
            result.append(roma)
        i += 1
    return "".join(result)


def kana_to_slug(kana: str) -> str | None:
    if not kana:
        return None
    kana_nfkc = normalize("NFKC", kana)
    tokens = [tok for tok in re.split(r"\s+", kana_nfkc.strip()) if tok]
    if not tokens:
        return None
    romaji_parts = []
    for token in tokens:
        roman = kana_token_to_romaji(token)
        if not roman:
            return None
        romaji_parts.append(roman)
    return "_".join(romaji_parts)


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    members = data["members"] if isinstance(data, dict) else data
    updated = 0
    for member in members:
        if member.get("slug"):
            continue
        slug = kana_to_slug(member.get("kana"))
        if not slug:
            slug = slugify_fallback(member.get("member_name", ""))
        member["slug"] = slug
        updated += 1
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated slug for {updated} members")


def slugify_fallback(name: str) -> str:
    nfkc = normalize("NFKC", name)
    ascii_chars = [ch for ch in nfkc if ch.isascii() and (ch.isalnum() or ch == ' ')]
    if ascii_chars:
        return "_".join("".join(ascii_chars).lower().split())
    hex_codepoints = "-".join(f"{ord(ch):x}" for ch in nfkc)
    return f"member-{hex_codepoints}"


if __name__ == "__main__":
    main()
