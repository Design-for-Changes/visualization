#!/usr/bin/env python3
"""Build an index of member speech counts from data/member_speeches."""
import json
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path('data/member_speeches')
OUTPUT = Path('data/member_speeches_index.json')

def main() -> None:
    index = {}
    for path in sorted(DATA_DIR.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            print(f"Skipping {path.name}: invalid JSON")
            continue
        slug = path.stem
        meetings = data.get('meetings') if isinstance(data, dict) else []
        meeting_count = len(meetings) if isinstance(meetings, list) else 0
        speech_count = 0
        if isinstance(meetings, list):
            for meeting in meetings:
                speeches = meeting.get('speeches') if isinstance(meeting, dict) else []
                if isinstance(speeches, list):
                    speech_count += len(speeches)
        index[slug] = {
            'meetings': meeting_count,
            'speeches': speech_count,
        }
    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'index': index,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Wrote index for {len(index)} members to {OUTPUT}")

if __name__ == '__main__':
    main()
