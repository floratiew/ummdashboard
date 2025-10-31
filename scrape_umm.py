#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

API_URL = "https://ummapi.nordpoolgroup.com/messages"
DEFAULT_OUTPUT = Path("UMM/data/umm_messages.csv")
FIELDNAMES = [
    "message_id",
    "version",
    "message_type",
    "event_status",
    "is_outdated",
    "publication_date",
    "event_start",
    "event_stop",
    "publisher_id",
    "publisher_name",
    "unavailability_type",
    "reason_code",
    "unavailability_reason",
    "cancellation_reason",
    "remarks",
    "areas_json",
    "market_participants_json",
    "assets_json",
    "generation_units_json",
    "production_units_json",
    "consumption_units_json",
    "transmission_units_json",
    "other_market_units_json",
    "acer_rss_message_ids_json",
    "planned_status",
    "retrieved_at",
]


@dataclass
class FetchConfig:
    status: str
    batch_size: int
    max_records: Optional[int]
    since: Optional[datetime]
    until: Optional[datetime]
    sleep: float


def parse_args() -> Tuple[FetchConfig, Path]:
    parser = argparse.ArgumentParser(
        description="Download Nord Pool UMM messages into a CSV file."
    )
    parser.add_argument(
        "--status",
        default="All",
        help="Status filter understood by the API (e.g. All, Active, Inactive).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2000,
        help="Number of items to request per API call (max observed 2000).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to the CSV file that will be written.",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Optional cap on how many records to download (useful for testing).",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Ignore messages published before this UTC date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--until",
        type=str,
        default=None,
        help="Ignore messages published after this UTC date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Delay in seconds between API calls to play nice with the service.",
    )

    args = parser.parse_args()
    since = datetime.fromisoformat(args.since) if args.since else None
    until = datetime.fromisoformat(args.until) if args.until else None
    if since and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    if until and until.tzinfo is None:
        until = until.replace(tzinfo=UTC)

    if since and until and since > until:
        parser.error("--since must be earlier than --until")

    cfg = FetchConfig(
        status=args.status,
        batch_size=args.batch_size,
        max_records=args.max_records,
        since=since,
        until=until,
        sleep=args.sleep,
    )

    return cfg, args.output


def iso_to_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def should_keep(publication_date: Optional[str], cfg: FetchConfig) -> bool:
    dt = iso_to_datetime(publication_date)
    if dt is None:
        return True
    if cfg.since and dt < cfg.since:
        return False
    if cfg.until and dt > cfg.until:
        return False
    return True


def serialize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def normalize_message(message: Dict[str, Any], retrieved_at: str) -> Dict[str, str]:
    return {
        "message_id": serialize(message.get("messageId")),
        "version": serialize(message.get("version")),
        "message_type": serialize(message.get("messageType")),
        "event_status": serialize(message.get("eventStatus")),
        "is_outdated": serialize(message.get("isOutdated")),
        "publication_date": serialize(message.get("publicationDate")),
        "event_start": serialize(message.get("eventStart")),
        "event_stop": serialize(message.get("eventStop")),
        "publisher_id": serialize(message.get("publisherId")),
        "publisher_name": serialize(message.get("publisherName")),
        "unavailability_type": serialize(message.get("unavailabilityType")),
        "reason_code": serialize(message.get("reasonCode")),
        "unavailability_reason": serialize(message.get("unavailabilityReason")),
        "cancellation_reason": serialize(message.get("cancellationReason")),
        "remarks": serialize(message.get("remarks")).replace("\r", " ").replace("\n", " "),
        "areas_json": serialize(message.get("areas")),
        "market_participants_json": serialize(message.get("marketParticipants")),
        "assets_json": serialize(message.get("assets")),
        "generation_units_json": serialize(message.get("generationUnits")),
        "production_units_json": serialize(message.get("productionUnits")),
        "consumption_units_json": serialize(message.get("consumptionUnits")),
        "transmission_units_json": serialize(message.get("transmissionUnits")),
        "other_market_units_json": serialize(message.get("otherMarketUnits")),
        "acer_rss_message_ids_json": serialize(message.get("acerRssMessageIds")),
        "planned_status": serialize(message.get("plannedStatus")),
        "retrieved_at": retrieved_at,
    }


def fetch_batch(
    status: str, limit: int, skip: int, session: requests.Session
) -> Tuple[List[Dict[str, Any]], int]:
    params = {"status": status, "limit": limit, "skip": skip}
    response = session.get(API_URL, params=params, timeout=60)
    if response.status_code == 405 and limit > 2000:
        raise ValueError(
            f"API rejected limit={limit}. Try using a value <= 2000 via --batch-size."
        )
    response.raise_for_status()
    data = response.json()
    items = data.get("items", [])
    total = data.get("total", skip + len(items))
    return items, int(total)


def fetch_message_detail(message_id: str, session: requests.Session) -> Dict[str, Any]:
    url = f"https://ummapi.nordpoolgroup.com/messages/{message_id}"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json() if response.content else {}


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_csv(rows: Iterable[Dict[str, str]], path: Path) -> None:
    ensure_parent_dir(path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def download_messages(cfg: FetchConfig) -> List[Dict[str, str]]:
    retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    collected: List[Dict[str, str]] = []
    skip = 0
    total: Optional[int] = None

    with requests.Session() as session:
        while True:
            items, reported_total = fetch_batch(cfg.status, cfg.batch_size, skip, session)
            if total is None:
                total = reported_total
                print(f"Total messages reported by API: {total}")

            if not items:
                break

            kept = 0
            for message in items:
                if not should_keep(message.get("publicationDate"), cfg):
                    continue
                message_id = str(message.get("messageId"))
                detail = fetch_message_detail(message_id, session) if message_id else {}
                # Only merge if detail is a dict
                if isinstance(detail, dict):
                    merged = {**message, **detail}
                else:
                    merged = message  # fallback: ignore detail if not a dict
                collected.append(normalize_message(merged, retrieved_at))
                kept += 1
                if cfg.max_records and len(collected) >= cfg.max_records:
                    print("Reached max-records limit. Stopping early.")
                    return collected

            skip += len(items)
            print(
                f"Fetched {skip}/{total} records "
                f"(kept {len(collected)} after local filtering)."
            )

            if total is not None and skip >= total:
                break

            if cfg.sleep:
                time.sleep(cfg.sleep)

    return collected


def main() -> int:
    cfg, output_path = parse_args()

    try:
        rows = download_messages(cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1

    if not rows:
        print("No rows collected; nothing written.")
        return 0

    write_csv(rows, output_path)
    print(f"Wrote {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
