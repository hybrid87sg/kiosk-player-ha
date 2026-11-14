"""A small client for the Kiosk server's relay API (/api/relay/v1)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from .const import DEFAULT_PORT

TIMEOUT = aiohttp.ClientTimeout(total=15)


class KioskError(Exception):
    """Something went wrong talking to the Kiosk server."""


class KioskConnectionError(KioskError):
    """The Kiosk server couldn't be reached."""


class KioskAuthError(KioskError):
    """The credential (or pairing code) was refused: 401, or 403 for a disabled relay."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class KioskNotFound(KioskError):
    """No such screen, or it isn't this relay's (the server answers both the same way)."""


class KioskRejected(KioskError):
    """The server refused a command, e.g. a playlist from another location."""


class KioskRateLimited(KioskError):
    """Too many pairing attempts."""


def normalize_url(typed: str) -> str:
    """'100.101.102.103' -> 'http://100.101.102.103:3000'. An https address or one with a port is kept."""
    text = (typed or "").strip().rstrip("/")
    if not text:
        return ""
    if "://" not in text:
        text = f"http://{text}"
    parts = urlsplit(text)
    netloc = parts.netloc
    if parts.scheme == "http" and parts.port is None and netloc:
        netloc = f"{netloc}:{DEFAULT_PORT}"
    return urlunsplit((parts.scheme, netloc, parts.path.rstrip("/"), "", ""))


async def _error_text(response: aiohttp.ClientResponse) -> str:
    try:
        body = await response.json(content_type=None)
        if isinstance(body, dict) and isinstance(body.get("error"), str):
            return body["error"]
    except (aiohttp.ContentTypeError, ValueError):
        pass
    return f"The Kiosk server answered {response.status}"


class KioskApi:
    """Talks to one main Kiosk server as one relay."""

    def __init__(self, session: aiohttp.ClientSession, url: str, credential: str) -> None:
        self.session = session
        self.url = url
        self.credential = credential

    @staticmethod
    async def pair(session: aiohttp.ClientSession, url: str, code: str, client: dict[str, Any]) -> dict[str, Any]:
        """Uses a pairing code once. Returns {relay, credential_id, credential, server}."""
        try:
            async with session.post(
                f"{url}/api/relay/v1/pair",
                json={"code": code, "kind": "control", "client": client},
                timeout=TIMEOUT,
            ) as response:
                if response.status == 201:
                    return await response.json()
                message = await _error_text(response)
                if response.status in (401, 403):
                    raise KioskAuthError(message, response.status)
                if response.status == 429:
                    raise KioskRateLimited(message)
                raise KioskError(message)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise KioskConnectionError(str(err) or type(err).__name__) from err

    async def _request(self, method: str, path: str, json: Any = None) -> Any:
        try:
            async with self.session.request(
                method,
                f"{self.url}{path}",
                json=json,
                headers={"Authorization": f"Bearer {self.credential}"},
                timeout=TIMEOUT,
            ) as response:
                if response.status < 300:
                    return await response.json()
                message = await _error_text(response)
                if response.status in (401, 403):
                    raise KioskAuthError(message, response.status)
                if response.status == 404:
                    raise KioskNotFound(message)
                if response.status == 422:
                    raise KioskRejected(message)
                raise KioskError(message)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise KioskConnectionError(str(err) or type(err).__name__) from err

    async def me(self) -> dict[str, Any]:
        return await self._request("GET", "/api/relay/v1/me")

    async def players(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/relay/v1/players")

    async def command(self, player_id: int, kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/relay/v1/players/{player_id}/commands", {"kind": kind, "payload": payload or {}}
        )

    async def heartbeat(self, version: str) -> dict[str, Any]:
        return await self._request("POST", "/api/relay/v1/heartbeat", {"version": version})

    def websocket_url(self, after: int | None) -> str:
        base = self.url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
        return f"{base}/api/relay/v1/ws" + (f"?after={after}" if after else "")
