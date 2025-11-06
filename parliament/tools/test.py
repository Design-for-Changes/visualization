from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Iterable

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
    ),
    "Referer": "https://www.shugiin.go.jp/",
}


def iter_urls(path: Path) -> Iterable[str]:
    return (u.strip() for u in path.read_text(encoding="utf-8").splitlines() if u.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Check question URL availability")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay seconds between requests")
    parser.add_argument("--limit", type=int, help="Only check the first N URLs")
    parser.add_argument("--timeout", type=float, default=20.0, help="Timeout seconds for each request")
    args = parser.parse_args()

    url_path = Path(__file__).parent / "question_url.txt"
    urls = list(iter_urls(url_path))
    if args.limit is not None:
        urls = urls[: args.limit]

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    ok, ng = [], []
    total = len(urls)

    for idx, url in enumerate(urls, 1):
        try:
            resp = session.get(url, timeout=args.timeout, allow_redirects=True)
            status = resp.status_code
            if 200 <= status < 300:
                ok.append((url, status))
                print(f"[{idx}/{total}] OK {status} {url}")
            else:
                ng.append((url, status, f"unexpected status ({status})"))
                print(f"[{idx}/{total}] NG {status} {url}")
        except requests.RequestException as exc:
            ng.append((url, None, str(exc)))
            print(f"[{idx}/{total}] NG {url} -> {exc}")
        time.sleep(max(args.delay, 0))

    print(f"Checked {total} URLs: {len(ok)} OK, {len(ng)} NG")
    if ng:
        print("--- Failures ---")
        for url, status, msg in ng:
            print(f"NG {status}: {url} -> {msg}")


if __name__ == "__main__":
    main()
