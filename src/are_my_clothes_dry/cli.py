"""Command-line entry point: watch the dryer's smart plug and notify via Pushover."""

import argparse
import asyncio
import logging
import os
import sys
import time

from .detector import CycleFinished, CycleStarted, DryerDetector
from .plug import Plug, PlugError
from .pushover import Pushover, PushoverError

TITLE = "Are my clothes dry?"
UNREACHABLE_ALERT_S = 300
COMMANDS = ("monitor", "power", "test-notify")

log = logging.getLogger("are_my_clothes_dry")


class ConfigError(Exception):
    pass


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    # journald timestamps each line itself
    fmt = "%(levelname)s %(message)s" if "JOURNAL_STREAM" in os.environ else "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format=fmt)
    try:
        asyncio.run(args.handler(args))
    except KeyboardInterrupt:
        pass
    except (ConfigError, PlugError, PushoverError) as e:
        sys.exit(f"error: {e}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true", help="log every power reading")

    parser = argparse.ArgumentParser(
        prog="are-my-clothes-dry",
        description="Send a Pushover notification when the dryer on a Tapo P110 plug finishes.",
    )
    commands = parser.add_subparsers(title="commands", metavar="COMMAND")

    monitor = commands.add_parser("monitor", parents=[common], help="watch the plug and notify (default)")
    monitor.set_defaults(handler=monitor_command)
    # String defaults are parsed with `type`, so bad env values get argparse's usual error.
    monitor.add_argument(
        "--threshold", type=float, metavar="WATTS", default=os.environ.get("DRYER_THRESHOLD_W", "10"),
        help="the dryer is running above this draw (default: %(default)s W)",
    )
    monitor.add_argument(
        "--idle-time", type=float, metavar="SECONDS", default=os.environ.get("DRYER_IDLE_TIME_S", "60"),
        help="how long it must stay at or below the threshold to count as finished (default: %(default)s s)",
    )
    monitor.add_argument(
        "--poll-interval", type=float, metavar="SECONDS", default=os.environ.get("DRYER_POLL_INTERVAL_S", "10"),
        help="time between readings (default: %(default)s s)",
    )

    power = commands.add_parser("power", parents=[common], help="print the current power draw and exit")
    power.set_defaults(handler=power_command)

    test_notify = commands.add_parser("test-notify", parents=[common], help="send a test notification and exit")
    test_notify.set_defaults(handler=test_notify_command)

    if not argv or (argv[0] not in COMMANDS and argv[0] not in ("-h", "--help")):
        argv = ["monitor", *argv]
    return parser.parse_args(argv)


async def monitor_command(args: argparse.Namespace) -> None:
    plug = plug_from_env()
    pushover = pushover_from_env()
    detector = DryerDetector(args.threshold, args.idle_time)
    log.info(
        "Watching plug at %s: running above %g W, finished after %gs idle",
        plug.host, args.threshold, args.idle_time,
    )

    failing_since: float | None = None
    alerted = False
    while True:
        try:
            watts = await plug.read_watts()
        except PlugError as e:
            now = time.monotonic()
            if failing_since is None:
                failing_since = now
            log.warning("%s", e)
            if not alerted and now - failing_since >= UNREACHABLE_ALERT_S:
                alerted = await notify(
                    pushover,
                    f"Can't reach the dryer's smart plug at {plug.host}. "
                    "Dryer notifications are paused until it's back.",
                )
        else:
            if failing_since is not None:
                log.info("Plug reachable again")
                failing_since = None
                alerted = False
            await handle_reading(detector, pushover, time.monotonic(), watts)
        await asyncio.sleep(args.poll_interval)


async def handle_reading(detector: DryerDetector, pushover: Pushover, now: float, watts: int) -> None:
    log.debug("%d W", watts)
    event = detector.update(now, watts)

    if isinstance(event, CycleStarted):
        log.info("Dryer started (%d W)", watts)
        await notify(pushover, "Dryer started.", priority=-1)
    elif isinstance(event, CycleFinished):
        duration = format_duration(event.duration_s)
        log.info("Dryer finished after %s", duration)
        await notify(pushover, f"Yes! The dryer finished after {duration}.")


async def notify(pushover: Pushover, message: str, priority: int = 0) -> bool:
    try:
        await pushover.send(TITLE, message, priority)
    except PushoverError as e:
        log.error("Notification failed: %s", e)
        return False
    log.info("Notification sent: %s", message)
    return True


async def power_command(args: argparse.Namespace) -> None:
    plug = plug_from_env()
    print(f"{await plug.read_watts()} W")


async def test_notify_command(args: argparse.Namespace) -> None:
    await pushover_from_env().send(TITLE, "Test notification from are-my-clothes-dry.")
    print("Test notification sent.")


def plug_from_env() -> Plug:
    username, password, host = require_env("TAPO_USERNAME", "TAPO_PASSWORD", "TAPO_HOST")
    return Plug(username, password, host)


def pushover_from_env() -> Pushover:
    token, user = require_env("PUSHOVER_TOKEN", "PUSHOVER_USER")
    return Pushover(token, user)


def require_env(*names: str) -> list[str]:
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise ConfigError(f"missing environment variables: {', '.join(missing)} (see .env.example)")
    return [os.environ[name] for name in names]


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    hours, minutes = divmod(round(seconds / 60), 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"
