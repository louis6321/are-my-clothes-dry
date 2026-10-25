"""Read power draw from a Tapo P110 over the local network."""

import asyncio

from tapo import ApiClient, PlugEnergyMonitoringHandler

# Per-request timeout inside the tapo library, and an outer limit per operation
# (connecting is a multi-request handshake).
REQUEST_TIMEOUT_S = 10
OPERATION_TIMEOUT_S = 30


class PlugError(Exception):
    pass


class Plug:
    def __init__(self, username: str, password: str, host: str) -> None:
        self.host = host
        self._username = username
        self._password = password
        self._device: PlugEnergyMonitoringHandler | None = None

    async def read_watts(self) -> int:
        """Return the current power draw in watts.

        Raises PlugError on any failure and drops the session, so the next call reconnects.
        """
        try:
            if self._device is None:
                client = ApiClient(self._username, self._password, timeout_s=REQUEST_TIMEOUT_S)
                self._device = await asyncio.wait_for(client.p110(self.host), OPERATION_TIMEOUT_S)
            result = await asyncio.wait_for(self._device.get_current_power(), OPERATION_TIMEOUT_S)
        except Exception as e:
            self._device = None
            raise PlugError(f"couldn't read plug at {self.host}: {str(e) or type(e).__name__}") from e
        return result.current_power
