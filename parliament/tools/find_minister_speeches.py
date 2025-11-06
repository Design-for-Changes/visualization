#!/usr/bin/env python3
"""Scan member speech JSON files for ministerial responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple


PARLIAMENT_DIR = Path(__file__).resolve().parent.parent
MEMBER_DIR = PARLIAMENT_DIR / "data/member_speeches"

ROLE_KEYWORDS = ("大臣", "副大臣", "政務官", "長官")


def extract_header(text: str) -> str | None:
    cleaned = text.lstrip()
    if not cleaned.startswith("○"):
        return None
    header = cleaned[1:].split("\n", 1)[0]
    header = header.split("　", 1)[0]
    header = header.split(" ", 1)[0]
    return header.strip()


def is_ministerial(header: str | None) -> bool:
    if not header:
        return False
    return any(keyword in header for keyword in ROLE_KEYWORDS)


def check_speeches(file_path: Path) -> List[Tuple[str, str, str, str]]:
    findings: List[Tuple[str, str, str, str]] = []
    data = json.loads(file_path.read_text(encoding="utf-8"))
    meetings = data.get("meetings")
    if not isinstance(meetings, list):
        return findings
    for meeting in meetings:
        issue_id = meeting.get("issueID") or ""
        date = meeting.get("date") or ""
        speeches = meeting.get("speeches")
        if not isinstance(speeches, list):
            continue
        for speech in speeches:
            speech_id = speech.get("speechID") or ""
            speech_text = speech.get("speech") or ""
            header = extract_header(speech_text)
            if is_ministerial(header):
                findings.append((issue_id, date, speech_id, header or ""))
    return findings


def main() -> None:
    files = sorted(MEMBER_DIR.glob("*.json"))
    total_hits = 0
    for file_path in files:
        results = check_speeches(file_path)
        if not results:
            continue
        total_hits += len(results)
        print(f"## {file_path.name} ({len(results)} hits)")
        for issue_id, date, speech_id, header in results:
            print(f"  - {issue_id} {date} {speech_id}: {header}")
    if total_hits == 0:
        print("No ministerial speeches found.")
    else:
        print(f"\nTotal ministerial speeches detected: {total_hits}")


if __name__ == "__main__":
    main()
