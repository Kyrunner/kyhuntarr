# KYHUNTARR

A personal fork of [NewtArr](https://github.com/elfhosted/newtarr) (itself a fork of [Huntarr](https://github.com/plexguide/Huntarr.io) v6.6.3), stripped down to only the apps I use and rebranded with a custom color scheme.

## Fork Lineage

**Huntarr v6.6.3** (plexguide) → **NewtArr** (ElfHosted) → **KYHUNTARR** (this repo)

- **Huntarr** was the original project, abandoned under controversial circumstances (telemetry, obfuscated code). See [this Reddit thread](https://www.reddit.com/r/selfhosted/comments/1rckopd/huntarr_your_passwords_and_your_entire_arr_stacks/?share_id=uq4GWZe3e0FNKUIXWHiq8) for context.
- **NewtArr** was ElfHosted's clean fork of Huntarr v6.6.3, the last release before the controversial changes.
- **KYHUNTARR** is my personal customization of NewtArr.

## What it does

KYHUNTARR continuously searches your *arr media libraries for missing content and items that need quality upgrades. It automatically triggers searches while being gentle on your indexers, helping you gradually complete your media collection.

| Application | Status |
| :---------- | :------------ |
| Sonarr | Supported |
| Radarr | Supported (with CF score upgrade fix) |
| Lidarr | Supported |

## Changes from NewtArr / Huntarr v6.6.3

- **Removed apps:** Readarr, Whisparr, Eros, Swaparr, Cleanuperr — only Radarr, Sonarr, and Lidarr remain
- **Rebranded** all Huntarr/NewtArr references to KYHUNTARR
- **Purple color scheme:** `#9b59b6` accent with near-black `#0d0d0d` dark theme (replaces ElfHosted green)
- **Custom icon:** Purple shield with white "KY" text
- **Radarr CF score upgrade fix:** Added `get_cf_upgrade_movies()` which finds movies that meet their quality cutoff but have custom format scores below the profile's `cutoffFormatScore`. Radarr's native `wanted/cutoff` API doesn't flag these. Also switched `get_cutoff_unmet_movies()` to use Radarr's proper `wanted/cutoff` endpoint instead of buggy client-side rank comparison.
- **GitHub Actions auto-build** to `ghcr.io/kyrunner/kyhuntarr:latest` on every push to main

## Running with Docker

```yaml
services:
  kyhuntarr:
    image: ghcr.io/kyrunner/kyhuntarr:latest
    container_name: kyhuntarr
    restart: unless-stopped
    ports:
      - "9705:9705"
    volumes:
      - ./config:/config
    environment:
      - TZ=America/New_York
```

The web UI is available on port 9705.

## Configuration

All configuration is done via the web UI. Settings are stored in `/config/`.

- **Apps**: Configure connections to your *arr instances (URL + API key)
- **Search Settings**: Control how many items to search per cycle, sleep duration, and API rate limits
- **Scheduling**: Set up automated search schedules

## License

GPL-3.0 — see [LICENSE](LICENSE). Fork of [Huntarr.io](https://github.com/plexguide/Huntarr.io) via [NewtArr](https://github.com/elfhosted/newtarr).
