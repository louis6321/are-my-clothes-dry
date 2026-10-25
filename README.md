# Are my clothes dry?

Watches a Tapo P110 smart plug that a clothes dryer is plugged into, and sends Pushover notifications:

- **Dryer started** (low priority, silent) as soon as it draws more than 10 W.
- **Dryer stopped** (normal priority) once it has stayed at or below 10 W for a minute. It doesn't claim the clothes are dry, because the dryer can also stop early, such as on a safety cut-out.

It keeps running and re-arms for the next load. Every "started" is followed by a "stopped", however short the run.

The plug is read over the local network, so this has to run on a machine on the same LAN as the plug (for example a Raspberry Pi).

## Setup

1. **Pushover:** copy your user key from the [Pushover dashboard](https://pushover.net), and [create an application](https://pushover.net/apps/build) to get an API token.
2. **Tapo plug:**
   - Find the plug's IP address in the Tapo app (device → ⚙ → Device info), and give it a DHCP reservation on your router so it doesn't change.
   - If authentication fails, turn on **Tapo app → Me → Tapo Lab → Third-Party Compatibility**.
   - The plug needs internet access to report energy data.
3. **Config:** `cp .env.example .env` and fill it in.
4. **Install** [uv](https://docs.astral.sh/uv/) (`brew install uv`, or `curl -LsSf https://astral.sh/uv/install.sh | sh` on Linux), then:

   ```sh
   uv sync
   uv run --env-file .env are-my-clothes-dry power         # should print the plug's current draw, e.g. "0 W"
   uv run --env-file .env are-my-clothes-dry test-notify   # should arrive on your phone
   uv run --env-file .env are-my-clothes-dry monitor -v    # watch it in the foreground
   ```

## Options

`monitor` takes these flags. Each can also be set in `.env`.

| Flag | Env var | Default | Meaning |
| --- | --- | --- | --- |
| `--threshold` | `DRYER_THRESHOLD_W` | 10 | The dryer counts as running above this many watts |
| `--idle-time` | `DRYER_IDLE_TIME_S` | 60 | Seconds at or below the threshold before it counts as stopped |
| `--poll-interval` | `DRYER_POLL_INTERVAL_S` | 10 | Seconds between readings |

If the plug can't be reached for 5 minutes, you get one notification saying so. It re-arms once the plug responds again.

## Running on a Raspberry Pi (systemd)

Any Pi from the Pi 2 / Zero 2 onward works. The `tapo` library is a compiled extension with prebuilt wheels for aarch64 and armv7, but not armv6, so the original Pi Zero and Pi 1 won't work.

Copy this folder to the Pi, for example with `rsync -av --exclude .venv ./ pi@raspberrypi.local:are-my-clothes-dry/`. Then, on the Pi:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
cd ~/are-my-clothes-dry
cp .env.example .env && nano .env      # skip if you copied your .env over
uv sync --frozen --no-dev
uv run --env-file .env are-my-clothes-dry power
```

Then install the service. Edit `User=` and the paths in `deploy/are-my-clothes-dry.service` first if your user isn't `pi`.

```sh
sudo cp deploy/are-my-clothes-dry.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now are-my-clothes-dry
journalctl -u are-my-clothes-dry -f
```

To update later: pull the changes, run `uv sync --frozen --no-dev`, then `sudo systemctl restart are-my-clothes-dry`.

## Development

```sh
uv run pytest
```

The cycle-detection logic in `src/are_my_clothes_dry/detector.py` is pure (no I/O) and fully covered by `tests/test_detector.py`.
