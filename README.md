# ⛺ Campwatch

A free, self-hosted Campnab. GitHub Actions runs [camply](https://github.com/juftin/camply) about every 10 minutes, sends a push notification through [Apprise](https://github.com/caronc/apprise) → [ntfy](https://ntfy.sh) when a sold-out campsite opens up, and publishes a status page to GitHub Pages.

## How it works

- `searches/*.yaml`: one camply YAML search per file. Add, edit or delete files to change what's watched.
- `watch.py`: runs every search, compares against `state/seen.json`, and alerts only on **newly opened** site/dates. A new search's first run is a silent baseline (it shows on the page but doesn't alert).
- `.github/workflows/watch.yml`: the schedule. It also runs on any push that changes a search, and from the Actions tab via **Run workflow**.
- `site/`: the Pages status page, which reads `status.json` written by each run.

## Adding a search

Copy one of the files in `searches/` and change the IDs and dates. To find a campground ID, use the number in its Recreation.gov URL (`recreation.gov/camping/campgrounds/232445`) or run:

```bash
pipx run camply campgrounds --search "watchman"
```

Useful options: `nights`, `weekends`, `days: [Friday, Saturday]`, `campsites` (specific site IDs), and `equipment`. See the [camply YAML docs](https://juftin.com/camply/command_line_usage/#searching-for-a-campsite-by-yaml-config). Other providers such as `ReserveCalifornia` work too.

## Alerts

The `APPRISE_URL` repo secret holds one or more [Apprise URLs](https://github.com/caronc/apprise/wiki), separated by spaces. The default is `ntfys://<secret-topic>`, so install the ntfy app and subscribe to that topic. To add email or Pushover, append its URL to the secret.

## Notes

- This only alerts. Book by hand, because automated booking breaks Recreation.gov's terms.
- GitHub can delay scheduled runs, and it pauses schedules in repos with no commits for 60 days. If that happens, re-enable the workflow from the Actions tab.
- Valley of Fire (Nevada State Parks) can't be watched: camply doesn't support that reservation system.
