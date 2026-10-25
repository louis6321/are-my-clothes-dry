"""Send notifications through the Pushover API."""

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.pushover.net/1/messages.json"
ATTEMPTS = 3
RETRY_DELAY_S = 5  # Pushover asks clients to wait at least 5 s before retrying
HTTP_TIMEOUT_S = 15

log = logging.getLogger(__name__)


class PushoverError(Exception):
    pass


class Pushover:
    def __init__(self, token: str, user: str) -> None:
        self._token = token
        self._user = user

    async def send(self, title: str, message: str, priority: int = 0) -> None:
        """Send a message, retrying network and server errors. Raises PushoverError on failure."""
        for attempt in range(1, ATTEMPTS + 1):
            try:
                await asyncio.to_thread(self._post, title, message, priority)
                return
            except urllib.error.HTTPError as e:
                if e.code < 500:
                    raise PushoverError(f"rejected ({e.code}): {_describe_errors(e)}") from e
                error: Exception = e
            except OSError as e:  # URLError, timeouts, connection resets
                error = e
            log.warning("Pushover attempt %d/%d failed: %s", attempt, ATTEMPTS, error)
            if attempt < ATTEMPTS:
                await asyncio.sleep(RETRY_DELAY_S * attempt)
        raise PushoverError(f"gave up after {ATTEMPTS} attempts: {error}")

    def _post(self, title: str, message: str, priority: int) -> None:
        data = urllib.parse.urlencode(
            {
                "token": self._token,
                "user": self._user,
                "title": title,
                "message": message,
                "priority": priority,
            }
        ).encode()
        with urllib.request.urlopen(API_URL, data=data, timeout=HTTP_TIMEOUT_S) as response:
            response.read()


def _describe_errors(error: urllib.error.HTTPError) -> str:
    try:
        return ", ".join(json.load(error)["errors"])
    except (ValueError, KeyError, TypeError):
        return error.reason
