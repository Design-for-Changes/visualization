#!/usr/bin/env python3
"""Fetch disability-related Diet speeches for members.

Usage:
    python tools/fetch_member_speeches.py [--limit 10] [--delay 1.5]

Creates JSON files under data/member_speeches/<slug>.json with structure:
{
  "member_name": "...",
  "kana": "...",
  "generated_at": "ISO8601",
  "keywords": [...],
  "meetings": [
    {
      "issueID": "...",
      "date": "2025-06-10",
      "nameOfMeeting": "...",
      "issue": "第10号",
      "session": 217,
      "speeches": [ { speech fields } ]
    }
  ]
}

See KEYWORDS for the search terms currently used.
"""
import argparse
import itertools
import json
import random
import re
import ssl
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from unicodedata import normalize
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from socket import timeout as SocketTimeout

try:
    import certifi  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    certifi = None

BASE_URL = "https://kokkai.ndl.go.jp/api/speech"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
    ),
    "Referer": "https://kokkai.ndl.go.jp/",
}
PAGE_SIZE = 100

KEYWORDS = [
    "障害福祉",
    "障害 福祉",
    "障がい 福祉",
    "障害者 福祉",
    "障がい者 福祉",
    "障害児 福祉",
    "障がい児 福祉",
    "医療的ケア児",
    "放課後等デイサービス",
    "特別児童扶養手当",
    "障害児福祉手当",
    "特別障害者手当",
]

DATA_DIR = Path("data/member_speeches")
MEMBERS_JSON = Path("data/diet_members_socials_enriched.json")
if certifi is not None:
    DEFAULT_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
else:  # pragma: no cover
    DEFAULT_SSL_CONTEXT = ssl.create_default_context()

SSL_CONTEXT: ssl.SSLContext = DEFAULT_SSL_CONTEXT


def load_members(limit: int | None = None) -> List[Dict]:
    data = json.loads(MEMBERS_JSON.read_text(encoding="utf-8"))
    members = data["members"] if isinstance(data, dict) else data
    filtered = [m for m in members if m.get("member_name")]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


def slugify(name: str) -> str:
    nfkc = normalize("NFKC", name)
    ascii_chars = [ch for ch in nfkc if ch.isascii() and ch.isalnum()]
    if ascii_chars:
        return "".join(ascii_chars).lower()
    # fallback: join code points for reproducible ASCII filename
    hex_codepoints = "-".join(f"{ord(ch):x}" for ch in nfkc)
    return f"member-{hex_codepoints}"


def fetch_member_speeches(member_name: str, delay: float, alt_names: List[str] | None = None) -> List[Dict]:
    speeches: Dict[str, Dict] = {}
    speaker_terms = [member_name]
    if alt_names:
        speaker_terms.extend(alt_names)

    for keyword in KEYWORDS:
        count = 0
        for speaker_term in speaker_terms:
            for record in paginate_speeches(speaker_term, keyword, delay):
                if record.get("nameOfMeeting") == "本会議":
                    continue
                if should_skip_record(record):
                    continue
                speech_id = record.get("speechID")
                if not speech_id:
                    continue
                speeches[speech_id] = record
                count += 1
        if count:
            print(f"    keyword '{keyword}': {count} hits", flush=True)
    return list(speeches.values())


def paginate_speeches(speaker_term: str, keyword: str, delay: float) -> Iterable[Dict]:
    start = 1
    while True:
        params = {
            "speaker": speaker_term,
            "any": keyword,
            "recordPacking": "json",
            "maximumRecords": PAGE_SIZE,
            "startRecord": start,
            "searchRange": "本文",
        }
        url = f"{BASE_URL}?{urlencode(params, doseq=True)}"
        req = Request(url, headers=HEADERS)
        for attempt in range(5):
            try:
                with urlopen(req, context=SSL_CONTEXT, timeout=30) as resp:
                    payload = json.load(resp)
                break
            except (ssl.SSLError, URLError, HTTPError, SocketTimeout, TimeoutError) as exc:
                if attempt == 4:
                    raise
                wait = max(delay, 1.0) * (attempt + 1)
                print(f"      retrying {speaker_term} '{keyword}' after error: {exc}", flush=True)
                sleep_with_jitter(wait)
        else:
            continue
        records = payload.get("speechRecord", [])
        for record in records:
            yield record
        next_pos = payload.get("nextRecordPosition")
        if not next_pos:
            break
        start = int(next_pos)
        sleep_with_jitter(delay)


def should_skip_record(record: Dict) -> bool:
    """Return True if the speech is purely procedural (e.g. chair statements)."""
    position = (record.get("speakerPosition") or "").strip()
    if position and any(key in position for key in ("委員長", "議長", "大臣")):
        return True
    speech_text = (record.get("speech") or "").lstrip()
    if speech_text.startswith("○"):
        head = speech_text[1:]
        head = head.split("\n", 1)[0]
        head = head.split("　", 1)[0]
        head = head.split(" ", 1)[0]
        if "委員長" in head or "議長" in head or "大臣" in head:
            return True
    return False


def sleep_with_jitter(delay: float) -> None:
    if delay <= 0:
        time.sleep(0)
        return
    jitter = random.uniform(0, delay / 2)
    time.sleep(delay + jitter)


def group_by_meeting(speeches: Iterable[Dict]) -> List[Dict]:
    meetings: Dict[str, Dict] = {}
    for speech in speeches:
        issue_id = speech.get("issueID") or f"{speech.get('date')}_{speech.get('nameOfMeeting')}"
        meeting = meetings.setdefault(
            issue_id,
            {
                "issueID": speech.get("issueID"),
                "date": speech.get("date"),
                "nameOfMeeting": speech.get("nameOfMeeting"),
                "issue": speech.get("issue"),
                "session": speech.get("session"),
                "speeches": [],
            },
        )
        meeting["speeches"].append(
            {
                key: speech.get(key)
                for key in (
                    "speechID",
                    "speechOrder",
                    "speaker",
                    "speech",
                    "speechURL",
                )
            }
        )
    for meeting in meetings.values():
        meeting["speeches"].sort(key=lambda s: s.get("speechOrder") or 0)
    return sorted(meetings.values(), key=lambda m: (m.get("date") or ""), reverse=True)


def save_member_file(member: Dict, meetings: List[Dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    slug = member.get("slug") or slugify(member["member_name"])
    path = DATA_DIR / f"{slug}.json"
    payload = {
        "member_name": member["member_name"],
        "kana": member.get("kana"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "keywords": KEYWORDS,
        "meetings": meetings,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Process only the first N members")
    parser.add_argument("--delay", type=float, default=3.0, help="Base delay between requests (seconds)")
    parser.add_argument("--insecure", action="store_true", help="Disable SSL verification (not recommended)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip members whose slug JSON already exists")
    args = parser.parse_args()

    global SSL_CONTEXT
    if args.insecure:
        print("Warning: SSL verification disabled", flush=True)
        SSL_CONTEXT = ssl._create_unverified_context()

    members = load_members(args.limit)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing_files = {p.stem for p in DATA_DIR.glob("*.json")}

    print(f"Processing {len(members)} members…")

    for idx, member in enumerate(members, start=1):
        name = member["member_name"]
        slug = member.get("slug") or slugify(member["member_name"])
        if args.skip_existing and slug in existing_files:
            print(f"[{idx}/{len(members)}] Skipping {name} (exists)", flush=True)
            continue

        print(f"[{idx}/{len(members)}] Fetching speeches for {name}…", flush=True)
        base_name = normalize("NFKC", name).replace(" ", "").replace("　", "")
        alt_names = []
        kana = member.get("kana")
        if kana:
            alt_names.append(normalize("NFKC", kana).replace(" ", "").replace("　", ""))
        speeches = fetch_member_speeches(base_name, args.delay, alt_names)
        if speeches:
            meetings = group_by_meeting(speeches)
            save_member_file(member, meetings)
            print(f"  -> saved {len(meetings)} meeting entries")
        else:
            print("  -> no matches")
        sleep_with_jitter(args.delay)
if __name__ == "__main__":
    main()
