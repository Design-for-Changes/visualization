#!/usr/bin/env python3
"""Post-process member speech JSON files to remove undesired records.

Removes meetings whose name is exactly "本会議" and drops empty meetings afterwards.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path("data/member_speeches")


def should_drop_meeting(meeting: dict) -> bool:
    name = meeting.get("nameOfMeeting") or meeting.get("meetingName")
    return name == "本会議"


def prune_meetings(meetings: list[dict]) -> list[dict]:
    cleaned = []
    for meeting in meetings:
        if should_drop_meeting(meeting):
            continue
        speeches = meeting.get("speeches")
        if isinstance(speeches, list):
            speeches = [s for s in speeches if s]
            meeting["speeches"] = speeches
        if not speeches:
            continue
        cleaned.append(meeting)
    return cleaned


def process_file(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    meetings = data.get("meetings")
    if not isinstance(meetings, list):
        return False

    original_count = len(meetings)
    new_meetings = prune_meetings(meetings)
    if len(new_meetings) == original_count:
        return False

    data["meetings"] = new_meetings
    data["postprocessed_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def main() -> None:
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        print("No member speech files found.")
        return

    updated = 0
    for file_path in files:
        if process_file(file_path):
            updated += 1
            print(f"updated {file_path.name}")

    print(f"Post-processing complete: {updated} files updated out of {len(files)}")


if __name__ == "__main__":
    main()
