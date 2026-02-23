# NewtArr

A neutered fork of [Huntarr](https://github.com/plexguide/Huntarr.io) v6.6.3, from simpler times, maintained by [ElfHosted](https://store.elfhosted.com).

## Why this fork?

The original Huntarr project was abandoned under controversial circumstances. The developer introduced telemetry, obfuscated code, and potential security concerns that led to significant community backlash. For context, see [this Reddit thread](https://www.reddit.com/r/selfhosted/comments/1rckopd/huntarr_your_passwords_and_your_entire_arr_stacks/?share_id=uq4GWZe3e0FNKUIXWHiq8).

NewtArr is based on v6.6.3, the last clean release before the controversial changes. It has been customized for use within [ElfHosted](https://store.elfhosted.com), but can be used standalone.

## Changes from upstream Huntarr v6.6.3

- Rebranded to "NewtArr"
- ElfHosted green color scheme
- Authentication disabled by default (designed for SSO-proxied deployments)
- Graceful Docker shutdown (no more hanging on SIGTERM)
- Dead documentation links replaced with tooltips
- Whisparr and Eros app sections un-hidden
- Radarr v5 API compatibility fix
- Upstream CI/telemetry/update-check code removed

## What it does

NewtArr continuously searches your *arr media libraries (Sonarr, Radarr, Lidarr, Readarr, Whisparr) for missing content and items that need quality upgrades. It automatically triggers searches while being gentle on your indexers, helping you gradually complete your media collection.

| Application | Status |
| :---------- | :------------ |
| Sonarr | Supported |
| Radarr | Supported |
| Lidarr | Supported |
| Readarr | Supported |
| Whisparr v2 | Supported |
| Whisparr v3 (Eros) | Supported |

## Running with Docker

```yaml
services:
  newtarr:
    image: ghcr.io/elfhosted/newtarr:latest
    container_name: newtarr
    restart: always
    ports:
      - "9705:9705"
    volumes:
      - ./config:/config
    environment:
      - TZ=UTC
```

The web UI is available on port 9705.

## Configuration

All configuration is done via the web UI. Settings are stored in `/config/`.

- **Apps**: Configure connections to your *arr instances (URL + API key)
- **Search Settings**: Control how many items to search per cycle, sleep duration, and API rate limits
- **Scheduling**: Set up automated search schedules

## License

This project is a fork of Huntarr.io. See [LICENSE](LICENSE) for details.
