#!/usr/bin/env python3
"""
Small Meta Marketing API helper for EletroCircular reporting.

Usage examples:
  python3 meta_ads_api.py adaccounts
  python3 meta_ads_api.py campaigns
  python3 meta_ads_api.py insights --since 2026-05-01 --until 2026-05-08 --level campaign
  python3 meta_ads_api.py leads --form-id 933999655646037 --since 2026-05-01 --until 2026-05-08
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_URL = "https://graph.facebook.com"
DEFAULT_VERSION = "v25.0"
DEFAULT_INSIGHT_FIELDS = [
    "campaign_id",
    "campaign_name",
    "adset_id",
    "adset_name",
    "ad_id",
    "ad_name",
    "objective",
    "spend",
    "impressions",
    "reach",
    "frequency",
    "clicks",
    "inline_link_clicks",
    "ctr",
    "inline_link_click_ctr",
    "cpc",
    "cost_per_inline_link_click",
    "cpm",
    "actions",
    "cost_per_action_type",
    "date_start",
    "date_stop",
]


class MetaApiError(RuntimeError):
    pass


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def graph_version() -> str:
    return os.getenv("META_GRAPH_VERSION", DEFAULT_VERSION).strip() or DEFAULT_VERSION


def graph_get(path_or_url: str, params: dict[str, Any] | None = None, retries: int = 3) -> dict[str, Any]:
    token = env_required("META_ACCESS_TOKEN")
    params = dict(params or {})
    params.setdefault("access_token", token)

    if path_or_url.startswith("https://"):
        url = path_or_url
        if "access_token=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{urllib.parse.urlencode({'access_token': token})}"
    else:
        path = path_or_url.lstrip("/")
        url = f"{BASE_URL}/{graph_version()}/{path}"
        url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"error": {"message": body}}
            error = payload.get("error", {})
            code = error.get("code")
            if exc.code in {500, 502, 503, 504} or code in {1, 2, 4, 17, 32, 613}:
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                    continue
            raise MetaApiError(json.dumps(payload, ensure_ascii=False, indent=2)) from exc
        except urllib.error.URLError as exc:
            if attempt < retries - 1:
                time.sleep(2**attempt)
                continue
            raise MetaApiError(str(exc)) from exc

    raise MetaApiError("Unexpected request failure")


def fetch_all(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    payload = graph_get(path, params)
    while True:
        rows.extend(payload.get("data", []))
        next_url = payload.get("paging", {}).get("next")
        if not next_url:
            break
        payload = graph_get(next_url)
    return rows


def ad_account_id() -> str:
    raw = env_required("META_AD_ACCOUNT_ID")
    return raw if raw.startswith("act_") else f"act_{raw}"


def flatten_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (dict, list)):
            flat[key] = json.dumps(value, ensure_ascii=False)
        else:
            flat[key] = value
    return flat


def write_outputs(rows: list[dict[str, Any]], stem: str) -> None:
    output_dir = Path("meta_api/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"{stem}_{stamp}.json"
    csv_path = output_dir / f"{stem}_{stamp}.csv"

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    flat_rows = [flatten_for_csv(row) for row in rows]
    fieldnames = sorted({key for row in flat_rows for key in row.keys()})
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)

    print(f"Rows: {len(rows)}")
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")


def command_adaccounts(_: argparse.Namespace) -> None:
    rows = fetch_all("me/adaccounts", {"fields": "id,account_id,name,account_status,currency,timezone_name", "limit": 100})
    write_outputs(rows, "adaccounts")


def command_campaigns(_: argparse.Namespace) -> None:
    rows = fetch_all(f"{ad_account_id()}/campaigns", {"fields": "id,name,status,effective_status,objective,created_time,updated_time", "limit": 100})
    write_outputs(rows, "campaigns")


def command_insights(args: argparse.Namespace) -> None:
    fields = args.fields.split(",") if args.fields else DEFAULT_INSIGHT_FIELDS
    params: dict[str, Any] = {
        "level": args.level,
        "fields": ",".join(fields),
        "time_range": json.dumps({"since": args.since, "until": args.until}),
        "limit": args.limit,
    }
    if args.time_increment:
        params["time_increment"] = args.time_increment
    rows = fetch_all(f"{ad_account_id()}/insights", params)
    write_outputs(rows, f"insights_{args.level}_{args.since}_{args.until}")


def command_leads(args: argparse.Namespace) -> None:
    fields = "id,created_time,ad_id,form_id,field_data,platform,campaign_id,adset_id"
    params: dict[str, Any] = {"fields": fields, "limit": args.limit}
    if args.since or args.until:
        filtering = []
        if args.since:
            filtering.append({"field": "time_created", "operator": "GREATER_THAN_OR_EQUAL", "value": int(datetime.fromisoformat(args.since).timestamp())})
        if args.until:
            filtering.append({"field": "time_created", "operator": "LESS_THAN_OR_EQUAL", "value": int(datetime.fromisoformat(args.until).timestamp())})
        params["filtering"] = json.dumps(filtering)
    rows = fetch_all(f"{args.form_id}/leads", params)
    write_outputs(rows, f"leads_{args.form_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Meta Marketing API reporting helper")
    sub = parser.add_subparsers(dest="command", required=True)

    adaccounts = sub.add_parser("adaccounts", help="List ad accounts available to the token")
    adaccounts.set_defaults(func=command_adaccounts)

    campaigns = sub.add_parser("campaigns", help="List campaigns for META_AD_ACCOUNT_ID")
    campaigns.set_defaults(func=command_campaigns)

    insights = sub.add_parser("insights", help="Export Ads Insights")
    insights.add_argument("--since", required=True, help="YYYY-MM-DD")
    insights.add_argument("--until", required=True, help="YYYY-MM-DD")
    insights.add_argument("--level", choices=["account", "campaign", "adset", "ad"], default="campaign")
    insights.add_argument("--time-increment", help="1 for daily rows, monthly for monthly rows")
    insights.add_argument("--fields", help="Comma-separated Meta insights fields")
    insights.add_argument("--limit", type=int, default=100)
    insights.set_defaults(func=command_insights)

    leads = sub.add_parser("leads", help="Export lead form submissions by form id")
    leads.add_argument("--form-id", required=True)
    leads.add_argument("--since", help="YYYY-MM-DD")
    leads.add_argument("--until", help="YYYY-MM-DD")
    leads.add_argument("--limit", type=int, default=100)
    leads.set_defaults(func=command_leads)

    return parser


def main() -> None:
    load_dotenv(Path("meta_api/.env"))
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except MetaApiError as exc:
        print(f"Meta API error:\n{exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
