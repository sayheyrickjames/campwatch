"""
Run every camply search in searches/, alert on newly opened sites, and
write the public status file for the Pages site.

Alerts go through Apprise (APPRISE_URL env var, e.g. ntfys://<topic>).
Each site/date is only alerted once while it stays available; if it gets
booked and opens up again later, it alerts again. A newly added search's
first run is a silent baseline.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import apprise
from camply.search import CAMPSITE_SEARCH_PROVIDER
from camply.utils.yaml_utils import yaml_file_to_arguments

ROOT = Path(__file__).parent
SEARCH_DIR = ROOT / "searches"
STATE_FILE = ROOT / "state" / "seen.json"
STATUS_FILE = ROOT / "site" / "status.json"
MAX_LINES = 8  # sites listed per alert before "and N more"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("campwatch")


def site_key(site) -> str:
    return f"{site.facility_id}:{site.campsite_id}:{site.booking_date:%Y-%m-%d}:{site.booking_nights}"


def run_search(path: Path):
    provider, provider_kwargs, _ = yaml_file_to_arguments(file_path=str(path))
    finder = CAMPSITE_SEARCH_PROVIDER[provider](**provider_kwargs)
    return finder.get_matching_campsites(log=False, continuous=False)


def describe(site) -> str:
    return (
        f"{site.facility_name} · site {site.campsite_site_name} · "
        f"{site.booking_date:%a %b %-d} for {site.booking_nights} night(s)"
    )


def notify(notifier, name: str, sites) -> None:
    lines = [describe(s) for s in sites[:MAX_LINES]]
    if len(sites) > MAX_LINES:
        lines.append(f"…and {len(sites) - MAX_LINES} more")
    body = "\n".join(lines)
    title = f"⛺ {len(sites)} site(s) opened: {name}"
    # ntfy turns this into a tap-to-open link on the notification
    url = sites[0].booking_url
    if notifier is None:
        log.warning("APPRISE_URL not set; would have sent:\n%s\n%s", title, body)
        return
    notifier.notify(title=title, body=f"{body}\n\nBook: {url}")


def main() -> int:
    seen = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    notifier = None
    if os.environ.get("APPRISE_URL"):
        notifier = apprise.Apprise()
        for target in os.environ["APPRISE_URL"].split():
            notifier.add(target)

    status = {"checked_at": datetime.now(timezone.utc).isoformat(), "searches": []}
    new_seen = {}
    failures = 0

    for path in sorted(SEARCH_DIR.glob("*.y*ml")):
        name = path.stem.replace("-", " ").replace("_", " ").title()
        entry = {"name": name, "file": path.name, "available": [], "error": None}
        try:
            sites = run_search(path)
        except Exception as exc:  # one broken search shouldn't stop the rest
            log.exception("Search %s failed", path.name)
            entry["error"] = str(exc)[:300]
            failures += 1
            # keep previous memory so a flaky API doesn't cause re-alerts
            if path.name in seen:
                new_seen[path.name] = seen[path.name]
            status["searches"].append(entry)
            continue

        keys = {site_key(s): s for s in sites}
        previously = set(seen.get(path.name, []))
        fresh = [s for k, s in keys.items() if k not in previously]
        log.info("%s: %d available, %d new", path.name, len(keys), len(fresh))
        if path.name not in seen:
            # first run of a new search: record a baseline (shown on the page),
            # only alert on openings from here on
            log.info("%s: first run, baseline recorded without alerting", path.name)
        elif fresh:
            notify(notifier, name, sorted(fresh, key=lambda s: s.booking_date))
        new_seen[path.name] = sorted(keys)
        entry["available"] = [
            {
                "campground": s.facility_name,
                "site": s.campsite_site_name,
                "loop": s.campsite_loop_name,
                "date": f"{s.booking_date:%Y-%m-%d}",
                "nights": s.booking_nights,
                "url": s.booking_url,
            }
            for s in sorted(sites, key=lambda s: (s.booking_date, s.facility_name))
        ]
        status["searches"].append(entry)

    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(new_seen, indent=2, sort_keys=True) + "\n")
    STATUS_FILE.parent.mkdir(exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, indent=2) + "\n")
    return 1 if failures and failures == len(status["searches"]) else 0


if __name__ == "__main__":
    sys.exit(main())
