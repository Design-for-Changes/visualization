#!/usr/bin/env python3
"""Remove ministerial responses from member speech JSON files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


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


def clean_file(path: Path) -> Tuple[int, int, List[Tuple[str, str, str]]]:
    """Return (meetings_removed, speeches_removed, removed_entries)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}") from exc

    meetings = data.get("meetings")
    if not isinstance(meetings, list):
        return 0, 0, []

    cleaned_meetings: List[Dict] = []
    meetings_removed = 0
    speeches_removed = 0
    removed_entries: List[Tuple[str, str, str]] = []

    for meeting in meetings:
        if not isinstance(meeting, dict):
            continue
        speeches = meeting.get("speeches")
        if not isinstance(speeches, list):
            continue

        issue_id = meeting.get("issueID") or ""
        date = meeting.get("date") or ""

        kept_speeches: List[Dict] = []
        for speech in speeches:
            if not isinstance(speech, dict):
                continue
            speech_id = speech.get("speechID") or ""
            header = extract_header(speech.get("speech") or "")
            if is_ministerial(header):
                speeches_removed += 1
                removed_entries.append((issue_id, date, speech_id))
                continue
            kept_speeches.append(speech)

        if kept_speeches:
            meeting = dict(meeting)
            meeting["speeches"] = kept_speeches
            cleaned_meetings.append(meeting)
        else:
            meetings_removed += 1

    if speeches_removed == 0 and meetings_removed == 0:
        return 0, 0, []

    data = dict(data)
    data["meetings"] = cleaned_meetings
    data["minister_speeches_cleaned_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return meetings_removed, speeches_removed, removed_entries


def main() -> None:
    total_meetings_removed = 0
    total_speeches_removed = 0
    total_files_updated = 0

    for path in sorted(MEMBER_DIR.glob("*.json")):
        meetings_removed, speeches_removed, removed_entries = clean_file(path)
        if speeches_removed == 0 and meetings_removed == 0:
            continue
        total_files_updated += 1
        total_meetings_removed += meetings_removed
        total_speeches_removed += speeches_removed
        print(f"{path.name}: removed {speeches_removed} speeches, {meetings_removed} meetings")
        for issue_id, date, speech_id in removed_entries:
            print(f"  - {issue_id} {date} {speech_id}")

    print()
    print(f"Updated {total_files_updated} files.")
    print(f"Total speeches removed: {total_speeches_removed}")
    print(f"Total empty meetings dropped: {total_meetings_removed}")


if __name__ == "__main__":
    main()
