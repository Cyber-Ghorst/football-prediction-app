"""Opponent-strength normalization using competition standings only."""
from __future__ import annotations


def attach_opponent_strength(matches: list[dict], standings: dict[int, float]) -> list[dict]:
    output = []
    for match in matches:
        item = dict(match)
        opponent_id = item.get("opponent_id")
        item["opponent_strength"] = standings.get(int(opponent_id)) if opponent_id is not None else None
        output.append(item)
    return output
