"""Stage 1a: Fetch and keyword-filter content from configured sources."""

import argparse
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import httpx
import trafilatura

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
CONFIG_DIR = ROOT / "config"
DATA_RAW = ROOT / "data" / "raw"

USER_AGENT = "Mozilla/5.0 (compatible; Scottish-VC-Tracker/1.0)"

GROUP_A = [
    "raise", "raised", "funding", "investment", "invested", "backed", "backer",
    "venture", "capital", "round", "seed", "series a", "series b", "series c",
    "pre-seed", "growth round", "angel",
]
GROUP_B = [
    "million", "£", "$m", "€m", "scotland", "scottish", "edinburgh",
    "glasgow", "aberdeen", "dundee",
]

ATOM_NS = "http://www.w3.org/2005/Atom"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


def _passes_filter(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in GROUP_A) and any(t in lower for t in GROUP_B)


def _parse_feed(xml_text: str) -> list:
    """Parse RSS 2.0 or Atom feed into a list of item dicts."""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    is_atom = ATOM_NS in root.tag or root.tag.lower() == "feed"

    if is_atom:
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            title_el = entry.find(f"{{{ATOM_NS}}}title")
            link_el = entry.find(f"{{{ATOM_NS}}}link")
            pub_el = (
                entry.find(f"{{{ATOM_NS}}}published")
                or entry.find(f"{{{ATOM_NS}}}updated")
            )
            sum_el = entry.find(f"{{{ATOM_NS}}}summary") or entry.find(
                f"{{{ATOM_NS}}}content"
            )
            items.append(
                {
                    "title": title_el.text if title_el is not None else None,
                    "link": link_el.get("href") if link_el is not None else None,
                    "published": pub_el.text if pub_el is not None else None,
                    "description": sum_el.text if sum_el is not None else None,
                }
            )
    else:
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            desc_el = item.find("description")
            content_el = item.find(f"{{{CONTENT_NS}}}encoded")
            description = (
                content_el.text if content_el is not None else None
            ) or (desc_el.text if desc_el is not None else None)
            items.append(
                {
                    "title": title_el.text if title_el is not None else None,
                    "link": link_el.text if link_el is not None else None,
                    "published": pub_el.text if pub_el is not None else None,
                    "description": description,
                }
            )

    return items


def _append_error(slug: str, url: str, error_msg: str, timestamp: str) -> None:
    errors_path = DATA_RAW / "errors.json"
    existing = []
    if errors_path.exists():
        try:
            existing = json.loads(errors_path.read_text())
        except Exception:
            existing = []
    existing.append({"source": slug, "url": url, "error": error_msg, "timestamp": timestamp})
    errors_path.write_text(json.dumps(existing, indent=2))


def _make_log_entry(slug: str) -> dict:
    return {
        "source_slug": slug,
        "url_fetched": "",
        "http_status": None,
        "items_found": 0,
        "items_passed_filter": 0,
        "candidates_added": 0,
        "text_extract_failures": 0,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _fetch_rss(client: httpx.Client, source: dict, candidates: list, log: dict) -> None:
    rss_url = source["rss_url"]
    log["url_fetched"] = rss_url

    rss_ok = False
    items = []
    try:
        resp = client.get(rss_url)
        log["http_status"] = resp.status_code
        resp.raise_for_status()
        items = _parse_feed(resp.text)
        rss_ok = True
    except Exception as e:
        log["error"] = f"RSS fetch failed: {e}"

    if not rss_ok or not items:
        # Fall back to direct URL fetch
        fallback_url = source["url"]
        try:
            resp2 = client.get(fallback_url)
            log["http_status"] = resp2.status_code
            resp2.raise_for_status()
            text = trafilatura.extract(resp2.text)
            log["items_found"] = 1
            if not text:
                log["text_extract_failures"] = 1
            elif _passes_filter(text[:2000]):
                candidates.append(
                    {
                        "source_slug": source["slug"],
                        "source_name": source["name"],
                        "url": fallback_url,
                        "title": None,
                        "published": None,
                        "text": text,
                    }
                )
                log["items_passed_filter"] = 1
                log["candidates_added"] = 1
        except Exception as e2:
            prior = log.get("error") or ""
            log["error"] = (prior + f"; fallback failed: {e2}").lstrip("; ")
        return

    log["items_found"] = len(items)
    passed = added = failures = 0

    for item in items:
        title = item.get("title") or ""
        description = item.get("description") or ""
        filter_text = (title + " " + description)[:2000]
        if not _passes_filter(filter_text):
            continue
        passed += 1

        link = item.get("link")
        article_text = None
        if link:
            try:
                article_resp = client.get(link)
                article_resp.raise_for_status()
                article_text = trafilatura.extract(article_resp.text)
            except Exception:
                pass

        if not article_text:
            failures += 1
            article_text = description or title

        if article_text:
            candidates.append(
                {
                    "source_slug": source["slug"],
                    "source_name": source["name"],
                    "url": link or source["url"],
                    "title": title or None,
                    "published": item.get("published") or None,
                    "text": article_text,
                }
            )
            added += 1

    log["items_passed_filter"] = passed
    log["candidates_added"] = added
    log["text_extract_failures"] = failures


def _fetch_page(client: httpx.Client, url: str, source: dict, candidates: list, log: dict) -> None:
    log["url_fetched"] = url
    log["items_found"] = 1

    try:
        resp = client.get(url)
        log["http_status"] = resp.status_code
        resp.raise_for_status()
    except Exception as e:
        log["error"] = str(e)
        return

    text = trafilatura.extract(resp.text)
    if not text:
        log["text_extract_failures"] = 1
        return

    if _passes_filter(text[:2000]):
        candidates.append(
            {
                "source_slug": source["slug"],
                "source_name": source["name"],
                "url": url,
                "title": None,
                "published": None,
                "text": text,
            }
        )
        log["items_passed_filter"] = 1
        log["candidates_added"] = 1


def _fetch_queries(client: httpx.Client, source: dict, candidates: list, log: dict) -> None:
    log["url_fetched"] = source["url"]
    queries = source.get("queries") or []
    total_found = total_passed = total_added = total_failures = 0
    last_status = None
    errors_list = []

    for i, query in enumerate(queries):
        if i > 0:
            time.sleep(2)
        url = f"{source['url']}?q={quote_plus(query)}"
        try:
            resp = client.get(url)
            last_status = resp.status_code
            resp.raise_for_status()
            total_found += 1
            text = trafilatura.extract(resp.text)
            if not text:
                total_failures += 1
                continue
            if _passes_filter(text[:2000]):
                candidates.append(
                    {
                        "source_slug": source["slug"],
                        "source_name": source["name"],
                        "url": url,
                        "title": None,
                        "published": None,
                        "text": text,
                    }
                )
                total_passed += 1
                total_added += 1
        except Exception as e:
            total_found += 1
            errors_list.append(f"query '{query}': {e}")

    log["http_status"] = last_status
    log["items_found"] = total_found
    log["items_passed_filter"] = total_passed
    log["candidates_added"] = total_added
    log["text_extract_failures"] = total_failures
    if errors_list:
        log["error"] = "; ".join(errors_list)


def _process_source(client: httpx.Client, source: dict, candidates: list) -> dict:
    log = _make_log_entry(source["slug"])
    try:
        if source.get("rss_url"):
            _fetch_rss(client, source, candidates, log)
        elif source.get("queries"):
            _fetch_queries(client, source, candidates, log)
        elif source.get("search_path"):
            url = source["url"].rstrip("/") + source["search_path"]
            _fetch_page(client, url, source, candidates, log)
        else:
            _fetch_page(client, source["url"], source, candidates, log)
    except Exception as e:
        log["error"] = str(e)
    return log


def run(date: str = None) -> dict:
    run_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_DIR / "sources.json") as f:
        sources = json.load(f)["sources"]

    candidates: list = []
    fetch_log: list = []

    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=15.0,
        follow_redirects=True,
    ) as client:
        for source in sources:
            log_entry = _process_source(client, source, candidates)
            fetch_log.append(log_entry)
            if log_entry.get("error"):
                _append_error(
                    source["slug"],
                    log_entry.get("url_fetched") or source.get("url", ""),
                    log_entry["error"],
                    log_entry["timestamp"],
                )

    candidates_path = DATA_RAW / f"{run_date}_candidates.json"
    candidates_path.write_text(json.dumps(candidates, indent=2, ensure_ascii=False))

    fetch_log_path = DATA_RAW / f"{run_date}_fetch_log.json"
    fetch_log_path.write_text(json.dumps(fetch_log, indent=2, ensure_ascii=False))

    errors = sum(1 for e in fetch_log if e.get("error"))
    sources_ok = len(fetch_log) - errors

    print(f"Fetcher complete: {len(candidates)} candidates from {sources_ok} sources ({errors} errors)")

    return {
        "candidates": len(candidates),
        "sources_ok": sources_ok,
        "errors": errors,
        "fallback_needed": len(candidates) == 0,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="Stage 1a: fetch and keyword-filter news sources")
    ap.add_argument("--date", default=None, help="Run date YYYY-MM-DD (default: today)")
    run(date=ap.parse_args().date)
