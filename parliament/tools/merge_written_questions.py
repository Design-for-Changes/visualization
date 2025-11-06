#!/usr/bin/env python3
"""Merge written-question listings into per-member speech JSON files.

For each entry in data/questions/written_question_listings.json, locate the
corresponding member file under data/member_speeches and append the question
metadata under a new ``written_questions`` array (deduplicating by question_id).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from unicodedata import normalize


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_JSON = PROJECT_ROOT / "data/questions/written_question_listings.json"
MEMBER_DIR = PROJECT_ROOT / "data/member_speeches"


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    text = normalize("NFKC", value)
    for ch in (" ", "　"):
        text = text.replace(ch, "")
    for suffix in ("君外", "君", "議員"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def load_question_listings(path: Path) -> List[Dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    listings = payload.get("listings") if isinstance(payload, dict) else None
    if not isinstance(listings, list):
        raise ValueError(f"Unexpected JSON structure in {path}")
    return [entry for entry in listings if isinstance(entry, dict)]


def build_member_index() -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    for file_path in MEMBER_DIR.glob("*.json"):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        member_name = data.get("member_name")
        key = normalize_name(member_name)
        if key:
            index[key] = file_path
    return index


def merge_questions(
    listings: Iterable[Dict],
    member_index: Dict[str, Path],
) -> Tuple[Dict[Path, List[Dict]], List[Dict]]:
    per_member: Dict[Path, List[Dict]] = defaultdict(list)
    unmatched: List[Dict] = []
    for entry in listings:
        key = normalize_name(entry.get("submitter"))
        file_path = member_index.get(key)
        if not file_path:
            unmatched.append(entry)
            continue
        per_member[file_path].append(entry)
    return per_member, unmatched


def dedupe_questions(existing: List[Dict], additions: Iterable[Dict]) -> List[Dict]:
    seen_ids = {}
    cleaned: List[Dict] = []
    for item in existing:
        if isinstance(item, dict):
            key = item.get("question_id") or (
                item.get("session"),
                item.get("number"),
                item.get("title"),
            )
            seen_ids[key] = item
            cleaned.append(item)
    for entry in additions:
        entry_copy = dict(entry)
        key = entry_copy.get("question_id") or (
            entry_copy.get("session"),
            entry_copy.get("number"),
            entry_copy.get("title"),
        )
        if key in seen_ids:
            seen_ids[key].update(entry_copy)
        else:
            seen_ids[key] = entry_copy
            cleaned.append(entry_copy)
    return cleaned


def update_member_files(
    assignments: Dict[Path, List[Dict]],
    dry_run: bool = False,
) -> Tuple[int, int]:
    updated_files = 0
    total_questions = 0
    for file_path, entries in assignments.items():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        existing_list = data.get("written_questions")
        if not isinstance(existing_list, list):
            existing_list = []
        merged_list = dedupe_questions(existing_list, entries)
        if merged_list == existing_list:
            continue
        data["written_questions"] = merged_list
        total_questions += len(merged_list)
        updated_files += 1
        if dry_run:
            continue
        data["written_questions_merged_at"] = datetime.now(timezone.utc).isoformat()
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return updated_files, total_questions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge written-question listings into per-member speech JSON files."
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=QUESTIONS_JSON,
        help="Path to written question listings JSON (default: data/questions/written_question_listings.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Display which files would change without modifying any JSON.",
    )
    args = parser.parse_args()

    listings = load_question_listings(args.questions)
    member_index = build_member_index()
    assignments, unmatched = merge_questions(listings, member_index)

    print(f"Loaded {len(listings)} listings.")
    print(f"Matched {sum(len(v) for v in assignments.values())} listings to member files.")
    if unmatched:
        print("Unmatched listings:")
        for entry in unmatched:
            submitter = entry.get("submitter")
            question_id = entry.get("question_id")
            print(f"  - {submitter} (question_id={question_id})")

    updated_files, total_questions = update_member_files(assignments, dry_run=args.dry_run)

    if args.dry_run:
        print(f"[dry-run] Would update {updated_files} member files.")
    else:
        print(f"Updated {updated_files} member files with written questions.")
    print(f"Total written question entries now stored: {total_questions}")


if __name__ == "__main__":
    main()
