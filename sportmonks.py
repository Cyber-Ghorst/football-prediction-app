"""Sportmonks Football API v3 adapter.

Credential: SPORTMONKS_API_TOKEN (Streamlit Secrets or environment).
Uses the documented v3 REST API and Authorization header. Current-season
collection is wired to Layer 2 with strict season/team identity and completeness gates.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
import time
from typing import Any, Mapping

import requests


class SportmonksError(RuntimeError):
    """Safe provider error; never includes token values or response bodies."""


class SportmonksClient:
    BASE_URL = "https://api.sportmonks.com/v3/football"

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str | None = None,
        timeout: int = 20,
    ):
        self.api_token = (
            api_token
            or os.getenv("SPORTMONKS_API_TOKEN")
            or os.getenv("SPORTMONKS_API_KEY")
        )
        if not self.api_token:
            try:
                import streamlit as st
                self.api_token = (
                    st.secrets.get("SPORTMONKS_API_TOKEN")
                    or st.secrets.get("SPORTMONKS_API_KEY")
                )
            except Exception:
                self.api_token = None
        if not self.api_token:
            raise SportmonksError(
                "Sportmonks token missing. Configure SPORTMONKS_API_TOKEN in Streamlit Secrets."
            )

        self.base_url = (base_url or os.getenv("SPORTMONKS_BASE_URL") or self.BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": self.api_token,
            "Accept": "application/json",
        })
        self.last_metadata: dict[str, Any] = {}

    def _get(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        request_started = time.monotonic()
        try:
            response = self.session.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=dict(params or {}),
                timeout=self.timeout,
            )
            self.last_metadata = {
                "request_path": path,
                "http_status": response.status_code,
                "request_seconds": round(time.monotonic() - request_started, 3),
                "rate_limit": response.headers.get("X-RateLimit-Limit"),
                "rate_remaining": response.headers.get("X-RateLimit-Remaining"),
            }
            if response.status_code in (401, 403):
                raise SportmonksError(
                    f"Sportmonks authentication or subscription access failed (HTTP {response.status_code})."
                )
            if response.status_code == 429:
                raise SportmonksError("Sportmonks rate limit reached (HTTP 429).")
            response.raise_for_status()
            payload = response.json()
        except SportmonksError:
            raise
        except requests.Timeout as exc:
            self.last_metadata = {
                "request_path": path,
                "http_status": None,
                "request_seconds": round(time.monotonic() - request_started, 3),
                "error": "timeout",
            }
            raise SportmonksError("Sportmonks request timed out.") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            self.last_metadata = {
                "request_path": path,
                "http_status": status,
                "request_seconds": round(time.monotonic() - request_started, 3),
                "error": type(exc).__name__,
            }
            suffix = f" (HTTP {status})" if status else ""
            raise SportmonksError(f"Sportmonks request to '{path}' failed{suffix}.") from exc
        except ValueError as exc:
            raise SportmonksError("Sportmonks returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise SportmonksError("Sportmonks returned an unexpected response schema.")
        if payload.get("message") and not isinstance(payload.get("data"), (list, dict)):
            raise SportmonksError("Sportmonks rejected the request; verify endpoint access and parameters.")
        return payload

    @staticmethod
    def _rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            rows = payload.get("data")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
            if isinstance(rows, dict):
                return [rows]
        return []

    def _all_pages(self, path: str, **params: Any) -> list[dict[str, Any]]:
        """Read a complete paginated collection or fail rather than use a partial season."""
        rows: list[dict[str, Any]] = []
        page = 1
        max_pages = 20
        while page <= max_pages:
            query = {**params, "per_page": min(int(params.get("per_page", 50)), 50), "page": page}
            payload = self._get(path, query)
            rows.extend(self._rows(payload))
            pagination = payload.get("pagination") or {}
            has_more = pagination.get("has_more")
            if has_more is None:
                # Some responses omit pagination when the collection fits one page.
                if len(self._rows(payload)) < query["per_page"]:
                    return rows
                raise SportmonksError("Sportmonks pagination metadata is missing; refusing a potentially incomplete dataset.")
            if not has_more:
                return rows
            page += 1
        raise SportmonksError("Sportmonks season collection exceeded the safe pagination limit; no partial dataset was accepted.")

    def leagues(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("leagues", params))

    def available_leagues(self, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages("leagues", **params)

    def teams_by_season(self, season_id: int | str, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages(f"teams/seasons/{season_id}", **params)

    def standings_by_season(self, season_id: int | str, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages(f"standings/seasons/{season_id}", **params)

    @staticmethod
    def _flatten_schedule_fixtures(payload: Any) -> list[dict[str, Any]]:
        """Flatten Sportmonks' stages -> rounds -> fixtures schedule response."""
        fixtures: list[dict[str, Any]] = []
        seen: set[int] = set()
        duplicate_ids: set[int] = set()
        for stage in SportmonksClient._rows(payload):
            for round_row in SportmonksClient._rows(stage.get("rounds")):
                for fixture_row in SportmonksClient._rows(round_row.get("fixtures")):
                    fixture = dict(fixture_row)
                    fixture.setdefault("stage_id", stage.get("id"))
                    fixture.setdefault("round_id", round_row.get("id"))
                    fixture_id = fixture.get("id")
                    if fixture_id is None:
                        continue
                    try:
                        key = int(fixture_id)
                    except (TypeError, ValueError):
                        continue
                    if key not in seen:
                        seen.add(key)
                        fixtures.append(fixture)
                    else:
                        duplicate_ids.add(key)
        duplicate_list = sorted(duplicate_ids)
        for fixture in fixtures:
            fixture["_schedule_duplicate_fixture_ids"] = duplicate_list
            fixture["_schedule_unique_fixture_count"] = len(seen)
        return fixtures

    @staticmethod
    def _fixture_team_ids(fixture: dict[str, Any]) -> set[int]:
        participants = SportmonksClient._rows(fixture.get("participants"))
        ids: set[int] = set()
        for participant in participants:
            try:
                if participant.get("id") is not None:
                    ids.add(int(participant["id"]))
            except (TypeError, ValueError):
                continue
        return ids

    @staticmethod
    def _fixture_kickoff_timestamp(fixture: dict[str, Any]) -> int | None:
        """Parse fixture kickoff into UTC epoch seconds for reliable ordering."""
        raw_timestamp = fixture.get("starting_at_timestamp")
        if raw_timestamp is not None:
            try:
                value = float(raw_timestamp)
                if value > 100_000_000_000:
                    value /= 1000
                return int(value)
            except (TypeError, ValueError, OverflowError):
                pass
        raw_date = fixture.get("starting_at")
        if not raw_date:
            return None
        try:
            parsed = datetime.fromisoformat(
                str(raw_date).strip().replace("Z", "+00:00")
            )
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return int(parsed.astimezone(timezone.utc).timestamp())
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _fixture_is_completed(fixture: dict[str, Any]) -> bool:
        """Recognize completed fixtures from either Sportmonks state IDs or labels."""
        try:
            if int(fixture.get("state_id")) in {5, 7, 8}:
                return True
        except (TypeError, ValueError):
            pass
        state = fixture.get("state") or fixture.get("status") or {}
        if isinstance(state, dict):
            label = state.get("short_name") or state.get("name") or ""
        else:
            label = state
        normalized = str(label).strip().casefold()
        return (
            normalized in {"ft", "aet", "pen", "finished", "full time",
                           "after extra time", "after penalties", "penalties"}
            or any(marker in normalized for marker in (
                "finished", "full time", "after extra", "after penalties"
            ))
        )

    def fixtures_by_season(
        self,
        season_id: int | str,
        *,
        include_statistics: bool = True,
        team_ids: list[int] | tuple[int, ...] | None = None,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """Fetch a season schedule and enrich selected-team history and the exact selected pairing.

        Schedule rows are the source of fixture IDs and kickoff times. The schedule
        response does not guarantee the related state/participant objects required
        by strict fixture verification, so the closest exact home/away pairing is
        hydrated regardless of whether it is scheduled, live, or completed.
        """
        if params:
            unsupported = ", ".join(sorted(params))
            raise SportmonksError(
                f"Unsupported schedule parameters ({unsupported}); the schedule endpoint does not accept query filters or includes."
            )
        payload = self._get(f"schedules/seasons/{season_id}")
        fixtures = self._flatten_schedule_fixtures(payload)
        # The endpoint is scoped to this season. Preserve request provenance
        # when nested schedule rows omit their own season_id.
        for fixture in fixtures:
            fixture.setdefault("season_id", int(season_id))

        selected_ids: set[int] = set()
        for value in team_ids or ():
            try:
                selected_ids.add(int(value))
            except (TypeError, ValueError):
                continue

        # Historical completed fixtures are enriched only when statistics were
        # requested. Preserve the existing limit of ten recent matches per team.
        chosen_completed: dict[int, dict[str, Any]] = {}
        if include_statistics and selected_ids:
            recent_by_team: dict[int, list[dict[str, Any]]] = {
                team_id: [] for team_id in selected_ids
            }
            for fixture in fixtures:
                if not self._fixture_is_completed(fixture):
                    continue
                for team_id in self._fixture_team_ids(fixture) & selected_ids:
                    recent_by_team[team_id].append(fixture)

            for team_fixtures in recent_by_team.values():
                ordered = sorted(
                    team_fixtures,
                    key=lambda row: (
                        self._fixture_kickoff_timestamp(row) is not None,
                        self._fixture_kickoff_timestamp(row) or 0,
                    ),
                    reverse=True,
                )
                for fixture in ordered[:10]:
                    if fixture.get("id") is not None:
                        chosen_completed[int(fixture["id"])] = fixture

        # Hydrate the closest exact home-v-away fixture for ledger identity.
        # This includes live and completed fixtures; the evaluator independently
        # compares prediction time with kickoff to prevent in-play forecasts scoring.
        selected_candidates: dict[int, dict[str, Any]] = {}
        if len(selected_ids) == 2:
            import time

            now = int(time.time())
            exact_rows = []
            for fixture in fixtures:
                try:
                    fixture_season = int(fixture.get("season_id"))
                    kickoff = self._fixture_kickoff_timestamp(fixture)
                    fixture_id = int(fixture.get("id"))
                    if kickoff is None:
                        continue
                except (TypeError, ValueError):
                    continue
                if fixture_season != int(season_id):
                    continue
                if self._fixture_team_ids(fixture) != selected_ids:
                    continue
                exact_rows.append((kickoff, fixture_id, fixture))
            future_rows = [row for row in exact_rows if row[0] > now]
            if future_rows:
                _, fixture_id, fixture = min(future_rows, key=lambda item: item[0])
                selected_candidates[fixture_id] = fixture
            elif exact_rows:
                _, fixture_id, fixture = max(exact_rows, key=lambda item: item[0])
                selected_candidates[fixture_id] = fixture

        # Merge both groups into one request, avoiding duplicate fixture IDs.
        detail_targets = dict(chosen_completed)
        detail_targets.update(selected_candidates)
        fixture_ids = sorted(detail_targets)
        if fixture_ids:
            include_parts = ["participants"]
            if chosen_completed:
                include_parts.append("scores")
            include_parts.extend(["state", "league", "season"])
            if chosen_completed:
                include_parts.append("statistics.type")

            # Smaller batches reduce the risk of Sportmonks rejecting long ID lists.
            # Print one concise progress line per request so Streamlit Cloud logs show
            # exactly which batch is running and how long each provider call takes.
            batch_size = 10
            batch_total = (len(fixture_ids) + batch_size - 1) // batch_size
            batch_specs = []
            for offset in range(0, len(fixture_ids), batch_size):
                fixture_batch = fixture_ids[offset:offset + batch_size]
                batch_number = (offset // batch_size) + 1
                batch_specs.append((
                    batch_number,
                    fixture_batch,
                    f"fixtures/multi/{','.join(str(value) for value in fixture_batch)}",
                ))

            # Respect instance-level transport overrides used by adapters and
            # tests; only the unmodified concrete HTTP client is parallelized.
            use_parallel_sessions = (
                type(self) is SportmonksClient and "_get" not in self.__dict__
            )

            def fetch_detail_batch(batch_spec):
                batch_number, fixture_batch, batch_path = batch_spec
                print(
                    f"[Sportmonks] Season {season_id}: starting detail batch "
                    f"{batch_number}/{batch_total} ({len(fixture_batch)} fixtures).",
                    flush=True,
                )
                if use_parallel_sessions:
                    # requests.Session is not shared across worker threads. Each
                    # concurrent batch gets its own short-lived authenticated
                    # session while retaining the same endpoint and include set.
                    with SportmonksClient(
                        api_token=self.api_token,
                        base_url=self.base_url,
                        timeout=self.timeout,
                    ) as batch_client:
                        details_payload = batch_client._get(
                            batch_path, {"include": ";".join(include_parts)}
                        )
                        metadata = dict(batch_client.last_metadata)
                else:
                    # Keep subclass/test doubles and custom clients on their
                    # established transport path.
                    details_payload = self._get(
                        batch_path, {"include": ";".join(include_parts)}
                    )
                    metadata = dict(getattr(self, "last_metadata", {}) or {})
                detail_rows = self._rows(details_payload)
                print(
                    f"[Sportmonks] Season {season_id}: completed detail batch "
                    f"{batch_number}/{batch_total}; HTTP {metadata.get('http_status')}; "
                    f"{len(detail_rows)} detail rows; "
                    f"{metadata.get('request_seconds', 'unknown')}s; "
                    f"rate remaining={metadata.get('rate_remaining')}.",
                    flush=True,
                )
                return detail_rows, metadata, batch_number

            if use_parallel_sessions and len(batch_specs) > 1:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(
                    max_workers=min(2, len(batch_specs))
                ) as detail_pool:
                    batch_results = list(detail_pool.map(fetch_detail_batch, batch_specs))
            else:
                batch_results = [fetch_detail_batch(spec) for spec in batch_specs]

            details_by_id: dict[int, dict[str, Any]] = {}
            for detail_rows, metadata, batch_number in batch_results:
                for row in detail_rows:
                    if row.get("id") is None:
                        continue
                    try:
                        details_by_id[int(row["id"])] = row
                    except (TypeError, ValueError):
                        continue

            # Merge only after all batches succeed; a failed batch must fail the
            # collection rather than silently accepting a partial history.
            from datetime import datetime, timezone
            details_fetched_at = datetime.now(timezone.utc).isoformat()
            for fixture_id, detail in details_by_id.items():
                base = detail_targets.get(fixture_id)
                if base is not None:
                    base.update(detail)
                    base["fixture_details_fetched_at"] = details_fetched_at
        collection_fetched_at = datetime.now(timezone.utc).isoformat()
        for fixture in fixtures:
            fixture["collection_fetched_at"] = collection_fetched_at
        return fixtures

    def seasons(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("seasons", params))

    def available_seasons(self, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages("seasons", **params)

    def teams(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("teams", params))

    def extended_squad_by_team(
        self, team_id: int | str, **params: Any
    ) -> list[dict[str, Any]]:
        """Fetch current and historical squad entries with the in_squad flag."""
        return self._rows(self._get(f"squads/teams/{team_id}/extended", params))

    def standings(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("standings", params))

    def fixtures(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("fixtures", params))

    def fixtures_between(self, start_date: str, end_date: str, **params: Any) -> list[dict[str, Any]]:
        """Fetch a date range; Sportmonks documents a maximum 100-day range."""
        return self._rows(self._get(f"fixtures/between/{start_date}/{end_date}", params))

    def fixture(self, fixture_id: int | str, **params: Any) -> dict[str, Any] | None:
        rows = self._rows(self._get(f"fixtures/{fixture_id}", params))
        return rows[0] if rows else None

    def livescores(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("livescores", params))

    def test_connection(self) -> dict[str, Any]:
        """Verify token access through the documented leagues endpoint."""
        rows = self.leagues(per_page=1)
        return {
            "transport_status": "responding",
            "records_returned": len(rows),
            "metadata": dict(self.last_metadata),
            "fallback_enabled": False,
            "note": "Connection verified; Layer 2 integration is present. Selected competition and season coverage must still be validated before use.",
        }

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "SportmonksClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
