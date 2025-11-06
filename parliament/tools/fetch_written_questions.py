#!/usr/bin/env python3
"""Fetch written question listings and filter them by disability-related keywords.

Reads Diet written-question listing URLs from tools/question_url.txt, scrapes each
page, and keeps only the entries whose title matches any of the configured keywords.
The filtered results are written to data/questions/written_question_listings.json.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from unicodedata import normalize
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
QUESTION_URLS_FILE = TOOLS_DIR / "question_url.txt"
OUTPUT_JSON = PROJECT_ROOT / "data/questions/written_question_listings.json"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
    )
}


def log(message: str) -> None:
    print(message, flush=True)


# Keywords supplied by the user request.
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

# Map the table headers in the listing HTML to our preferred field names.
HEADER_TEXT_MAP = {
    "SHITSUMON.NUMBER": "number",
    "SHITSUMON.KENMEI": "title",
    "SHITSUMON.TEISHUTSUSHA": "submitter",
    "SHITSUMON.STATUS": "status",
}

HEADER_LINK_MAP = {
    "SHITSUMON.KLINK": "history_url",
    "SHITSUMON.SLINK": "question_html_url",
    "SHITSUMON.SLINKPDF": "question_pdf_url",
    "SHITSUMON.TLINK": "answer_html_url",
    "SHITSUMON.TLINKPDF": "answer_pdf_url",
}


@dataclass
class ListingRow:
    """Structured information extracted from a listing table row."""

    number: Optional[int]
    title: str
    submitter: Optional[str]
    status: Optional[str]
    history_url: Optional[str]
    question_html_url: Optional[str]
    question_pdf_url: Optional[str]
    answer_html_url: Optional[str]
    answer_pdf_url: Optional[str]
    source_listing_url: str
    session: Optional[int]
    matched_keywords: List[str]


class WrittenQuestionListingParser(HTMLParser):
    """Minimal HTML parser tailored for the written-question listing tables."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.rows: List[Dict[str, str]] = []
        self._in_tr = False
        self._current_row: Dict[str, str] = {}
        self._current_header: Optional[str] = None
        self._text_chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        attr_dict = {k.lower(): v for k, v in attrs}
        tag = tag.lower()
        if tag == "tr":
            self._start_row()
        elif self._in_tr and tag == "td":
            header = attr_dict.get("headers")
            self._current_header = header.upper() if header else None
            self._text_chunks = []
        elif self._in_tr and tag == "a" and self._current_header:
            href = attr_dict.get("href")
            if href:
                self._store_link(href)
        elif self._in_tr and tag == "br" and self._current_header:
            self._text_chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "td" and self._in_tr and self._current_header:
            self._store_text()
            self._current_header = None
            self._text_chunks = []
        elif tag == "tr" and self._in_tr:
            self._finalize_row()

    def handle_data(self, data: str) -> None:
        if self._in_tr and self._current_header:
            stripped = data.strip()
            if stripped:
                self._text_chunks.append(stripped)

    # Internal helpers -----------------------------------------------------

    def _start_row(self) -> None:
        self._in_tr = True
        self._current_row = {}
        self._current_header = None
        self._text_chunks = []

    def _finalize_row(self) -> None:
        if self._current_row.get("title"):
            self.rows.append(self._current_row)
        self._in_tr = False
        self._current_row = {}
        self._current_header = None
        self._text_chunks = []

    def _store_text(self) -> None:
        if not self._current_header:
            return
        key = HEADER_TEXT_MAP.get(self._current_header)
        if not key:
            return
        text = " ".join(chunk for chunk in self._text_chunks if chunk).strip()
        if text:
            self._current_row[key] = text

    def _store_link(self, href: str) -> None:
        if not self._current_header:
            return
        key = HEADER_LINK_MAP.get(self._current_header)
        if not key:
            return
        # Only keep the first link per cell – later ones are duplicates such as "(HTML)" labels.
        self._current_row.setdefault(key, urljoin(self.base_url, href))


def normalize_for_search(text: str) -> str:
    """Normalize strings for consistent keyword matching."""
    nfkc = normalize("NFKC", text)
    collapsed = re.sub(r"\s+", " ", nfkc).strip()
    return collapsed


def build_keyword_variants(keywords: Iterable[str]) -> List[tuple[str, str]]:
    """Return (original keyword, normalized variant) pairs for matching."""
    variants: List[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for kw in keywords:
        norm_kw = normalize_for_search(kw)
        for candidate in {norm_kw, norm_kw.replace(" ", "")}:
            key = (kw, candidate)
            if candidate and key not in seen:
                variants.append(key)
                seen.add(key)
    return variants


KEYWORD_VARIANTS = build_keyword_variants(KEYWORDS)


def fetch_listing(url: str, *, retries: int = 3, delay: float = 1.0) -> str:
    """Download a listing page and decode it into text."""
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        log(f"      Attempt {attempt} for {url}")
        try:
            req = Request(url, headers=REQUEST_HEADERS)
            with urlopen(req, timeout=30) as resp:
                raw = resp.read()
            return raw.decode("shift_jis", errors="replace")
        except (HTTPError, URLError) as exc:
            last_error = exc
            log(f"      -> attempt {attempt} failed: {exc}")
            if attempt == retries:
                break
            backoff = delay * attempt
            log(f"      -> retrying after {backoff:.2f}s delay")
            time.sleep(delay * attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error


def parse_listing(html: str, url: str) -> List[Dict[str, str]]:
    parser = WrittenQuestionListingParser(url)
    parser.feed(html)
    return parser.rows


def extract_session(url: str) -> Optional[int]:
    """Derive the Diet session (会期) number from the listing URL."""
    match = re.search(r"kaiji(\d+)_", url)
    if match:
        return int(match.group(1))
    return None


def parse_number(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def compute_question_id(question_url: Optional[str]) -> Optional[str]:
    if not question_url:
        return None
    match = re.search(r"/([ab]\d{6})\.[Hh][Tt][Mm]$", question_url)
    if match:
        return match.group(1)
    return None


def match_keywords(title: str) -> List[str]:
    normalized = normalize_for_search(title).lower()
    compact = normalized.replace(" ", "")
    matches: List[str] = []
    for original, variant in KEYWORD_VARIANTS:
        target = compact if " " not in variant else normalized
        if variant.lower() in target:
            if original not in matches:
                matches.append(original)
    return matches


def load_urls(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"URL list not found: {path}")
    urls: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            urls.append(stripped)
    return urls


def build_listing_rows(urls: Iterable[str], delay: float) -> List[ListingRow]:
    rows: List[ListingRow] = []
    url_list = list(urls)
    total = len(url_list)
    log(f"Processing {total} listing URLs.")
    for idx, url in enumerate(url_list, start=1):
        session = extract_session(url)
        session_label = session if session is not None else "?"
        log(f"[{idx}/{total}] Fetching session {session_label}: {url}")
        try:
            html = fetch_listing(url)
        except Exception as exc:
            log(f"  !! Failed to fetch {url}: {exc}")
            continue
        parsed_rows = parse_listing(html, url)
        log(f"  Parsed {len(parsed_rows)} table rows")
        matches_this_url = 0
        for row in parsed_rows:
            title = row.get("title")
            if not title:
                continue
            matched = match_keywords(title)
            if not matched:
                continue
            number = parse_number(row.get("number"))
            display_number = number if number is not None else "?"
            listing_row = ListingRow(
                number=number,
                title=title,
                submitter=row.get("submitter"),
                status=row.get("status"),
                history_url=row.get("history_url"),
                question_html_url=row.get("question_html_url"),
                question_pdf_url=row.get("question_pdf_url"),
                answer_html_url=row.get("answer_html_url"),
                answer_pdf_url=row.get("answer_pdf_url"),
                source_listing_url=url,
                session=session,
                matched_keywords=matched,
            )
            rows.append(listing_row)
            matches_this_url += 1
            keyword_display = ", ".join(matched)
            log(f"    ✓ #{display_number} {title} (keywords: {keyword_display})")
        if matches_this_url == 0:
            log("    No keyword matches found in this listing.")
        else:
            log(f"    -> {matches_this_url} matches found in this listing.")
        if delay > 0 and idx != total:
            log(f"  Waiting {delay:.2f}s before next request.")
            time.sleep(delay)
    log(f"Finished processing listings. Total matched rows: {len(rows)}")
    return rows


def deduplicate_rows(rows: Iterable[ListingRow]) -> List[ListingRow]:
    """Deduplicate entries using question IDs or a composite of session/number/title."""
    seen: Dict[str, ListingRow] = {}
    for row in rows:
        key = compute_question_id(row.question_html_url)
        if not key:
            key = f"{row.session}:{row.number}:{normalize_for_search(row.title)}"
        if key not in seen:
            seen[key] = row
        else:
            # Merge keyword matches if duplicates occur.
            existing = seen[key]
            for kw in row.matched_keywords:
                if kw not in existing.matched_keywords:
                    existing.matched_keywords.append(kw)
    return list(seen.values())


def serialize_rows(rows: Iterable[ListingRow]) -> List[Dict[str, object]]:
    serialized: List[Dict[str, object]] = []
    for row in rows:
        payload: Dict[str, object] = {
            "session": row.session,
            "number": row.number,
            "title": row.title,
            "submitter": row.submitter,
            "status": row.status,
            "matched_keywords": row.matched_keywords,
            "source_listing_url": row.source_listing_url,
        }
        question_id = compute_question_id(row.question_html_url)
        if question_id:
            payload["question_id"] = question_id
        if row.history_url:
            payload["history_url"] = row.history_url
        if row.question_html_url:
            payload["question_html_url"] = row.question_html_url
        if row.question_pdf_url:
            payload["question_pdf_url"] = row.question_pdf_url
        if row.answer_html_url:
            payload["answer_html_url"] = row.answer_html_url
        if row.answer_pdf_url:
            payload["answer_pdf_url"] = row.answer_pdf_url
        serialized.append(payload)
    return sorted(
        serialized,
        key=lambda item: (
            -(item.get("session") or 0),
            item.get("number") or 0,
            item.get("title") or "",
        ),
    )


def save_results(rows: List[ListingRow], output_path: Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "House of Representatives written questions",
        "keywords": KEYWORDS,
        "listings": serialize_rows(rows),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"Saving results to {output_path}")
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Diet written-question listings and filter by keywords."
    )
    parser.add_argument(
        "--urls",
        type=Path,
        default=QUESTION_URLS_FILE,
        help="Path to a text file containing listing URLs (default: tools/question_url.txt).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_JSON,
        help="Destination JSON file (default: data/questions/written_question_listings.json).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay in seconds between requests (default: 0.5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on the number of listing URLs to process.",
    )
    args = parser.parse_args(argv)

    urls = load_urls(args.urls)
    if args.limit is not None:
        urls = urls[: args.limit]

    listing_rows = build_listing_rows(urls, delay=args.delay)
    deduped_rows = deduplicate_rows(listing_rows)
    log(
        "Deduplicated matches: "
        f"{len(deduped_rows)} unique entries from {len(listing_rows)} raw matches."
    )
    save_results(deduped_rows, args.output)
    print(f"Wrote {len(deduped_rows)} matches to {args.output}")


if __name__ == "__main__":
    main()
