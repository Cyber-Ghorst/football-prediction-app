"""Read-only OpenScores football-data adapter.

OpenScores is a secondary corroboration source. This module deliberately returns
provider payloads with provenance metadata and does not normalize them into
production prediction inputs.

Configure OPENSCORES_API_KEY (an osk_live_* key) in the deployment secrets.
The documented MCP URL's trailing slash is intentional.
"""
from __future__ import annotations

from datetime import datetime, timezone
import itertools
import json
import os
from typing import Any

import requests


class OpenScoresError(RuntimeError):
    """Sanitized OpenScores transport, authentication, or response error."""


class OpenScoresClient:
    """Small synchronous client for OpenScores' documented read-only MCP tools."""

    ENDPOINT = "https://api.openscores.ai/mcp/"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 15,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENSCORES_API_KEY")
        if isinstance(self.api_key, str):
            self.api_key = self.api_key.strip()
        if not self.api_key:
            try:
                import streamlit as st

                self.api_key = st.secrets.get("OPENSCORES_API_KEY")
            except Exception:
                self.api_key = None
        if isinstance(self.api_key, str):
            self.api_key = self.api_key.strip()
        if not self.api_key:
            raise OpenScoresError(
                "OpenScores API key missing. Configure OPENSCORES_API_KEY in deployment secrets."
            )

        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
        )
        self._request_ids = itertools.count(1)
        self.last_metadata: dict[str, Any] = {}

    @staticmethod
    def _decode_response(response: requests.Response) -> dict[str, Any]:
        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "text/event-stream" not in content_type:
            payload = response.json()
            if not isinstance(payload, dict):
                raise OpenScoresError("OpenScores returned an unexpected JSON-RPC response.")
            return payload

        # Streamable HTTP may return JSON-RPC messages as Server-Sent Events.
        messages: list[dict[str, Any]] = []
        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                item = json.loads(raw)
            except ValueError:
                continue
            if isinstance(item, dict):
                messages.append(item)
        if not messages:
            raise OpenScoresError("OpenScores returned an empty event stream.")
        return messages[-1]

    @staticmethod
    def _extract_tool_data(result: dict[str, Any]) -> Any:
        if result.get("isError"):
            raise OpenScoresError("OpenScores reported a tool execution error.")

        if "structuredContent" in result:
            return result["structuredContent"]

        content = result.get("content")
        if isinstance(content, list):
            text_blocks = [
                block.get("text")
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ]
            if len(text_blocks) == 1:
                try:
                    return json.loads(text_blocks[0])
                except ValueError:
                    return text_blocks[0]
            if text_blocks:
                decoded: list[Any] = []
                for item in text_blocks:
                    try:
                        decoded.append(json.loads(item))
                    except ValueError:
                        decoded.append(item)
                return decoded
        return result

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call one documented read-only tool and retain source provenance."""
        request_id = next(self._request_ids)
        body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        self.last_metadata = {}
        try:
            response = self.session.post(
                self.ENDPOINT,
                json=body,
                timeout=self.timeout,
                allow_redirects=False,
            )
            self.last_metadata = {
                "http_status": response.status_code,
                "request_id": request_id,
                "tool": name,
                "retry_after": response.headers.get("Retry-After"),
            }
            if response.status_code in (401, 403):
                raise OpenScoresError(
                    f"OpenScores authentication/access failed (HTTP {response.status_code})."
                )
            if response.status_code == 429:
                raise OpenScoresError(
                    "OpenScores rate limit reached (HTTP 429); respect Retry-After before retrying."
                )
            response.raise_for_status()
            envelope = self._decode_response(response)
            if "error" in envelope:
                error = envelope.get("error")
                message = error.get("message") if isinstance(error, dict) else None
                safe_message = str(message or "JSON-RPC request failed")[:180]
                raise OpenScoresError(f"OpenScores tool request failed: {safe_message}.")
            result = envelope.get("result")
            if not isinstance(result, dict):
                raise OpenScoresError("OpenScores response did not contain a valid tool result.")
            data = self._extract_tool_data(result)
            return {
                "provider": "openscores",
                "source_endpoint": f"mcp.tools/call:{name}",
                "attribution": "OpenScores (https://openscores.ai/)",
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }
        except OpenScoresError:
            raise
        except requests.Timeout as exc:
            raise OpenScoresError("OpenScores request timed out.") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise OpenScoresError(f"OpenScores network request failed{suffix}.") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise OpenScoresError("OpenScores returned invalid JSON.") from exc

    def list_leagues(self) -> dict[str, Any]:
        return self.call_tool("list_leagues")

    def list_seasons(self, league_id: int | str) -> dict[str, Any]:
        return self.call_tool("list_seasons", {"league_id": league_id})

    def list_fixtures(self, **filters: Any) -> dict[str, Any]:
        return self.call_tool("list_fixtures", filters)

    def get_fixture(self, fixture_id: int | str) -> dict[str, Any]:
        return self.call_tool("get_fixture", {"fixture_id": fixture_id})

    def get_standings(self, season_id: int | str) -> dict[str, Any]:
        return self.call_tool("get_standings", {"season_id": season_id})

    def search_teams(self, query: str) -> dict[str, Any]:
        return self.call_tool("search_teams", {"q": query})

    def get_team(self, team_id: int | str) -> dict[str, Any]:
        return self.call_tool("get_team", {"team_id": team_id})

    def search_players(
        self,
        query: str,
        nationality: str | None = None,
        position: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {"q": query}
        if nationality:
            arguments["nationality"] = nationality
        if position:
            arguments["position"] = position
        return self.call_tool("search_players", arguments)

    def get_player(self, player_id: int | str) -> dict[str, Any]:
        return self.call_tool("get_player", {"player_id": player_id})

    def test_connection(self) -> dict[str, Any]:
        """Check authenticated connectivity without changing remote or app data."""
        result = self.list_leagues()
        data = result.get("data")
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            count = len(data["items"])
        elif isinstance(data, list):
            count = len(data)
        else:
            count = None
        return {
            "status": "connected",
            "league_count_returned": count,
            "provider": "openscores",
            "retrieved_at_utc": result["retrieved_at_utc"],
        }

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "OpenScoresClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
