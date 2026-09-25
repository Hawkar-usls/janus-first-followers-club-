from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import floor, sqrt
from typing import Any, Mapping


class RewardError(ValueError):
    pass


DAILY_CYCLE = {
    1: {"janus_coin": 25, "xp": 10},
    2: {"janus_coin": 30, "xp": 10},
    3: {"janus_coin": 35, "xp": 15},
    4: {"janus_coin": 40, "xp": 15},
    5: {"janus_coin": 50, "xp": 20},
    6: {"janus_coin": 60, "xp": 20},
    7: {"janus_coin": 100, "xp": 40, "item": "PORTAL_DAILY_CHEST"},
}

ACTIVITY = {
    "GROUP_DAILY_PARTICIPATION": {"xp": 15, "janus_coin": 10, "daily_cap": 1},
    "GROUP_ACCEPTED_CONTRIBUTION": {"xp": 75, "janus_coin": 75, "daily_cap": 3},
    "GENESIS_DAILY_PLAY": {"xp": 20, "janus_coin": 10, "daily_cap": 1},
    "GENESIS_QUEST_COMPLETE": {"xp": 50, "janus_coin": 40, "daily_cap": 10},
    "HRAIN_GRAPH_SAVE": {"xp": 15, "janus_coin": 5, "daily_cap": 1},
    "INAIHR_ACCEPTED_SYNTH": {"xp": 20, "janus_coin": 5, "daily_cap": 1},
    "MARKET_COMPLETED_FREE_SEARCH": {"xp": 30, "janus_coin": 20, "lifetime_cap": 1},
    "MARKET_COMPLETED_PAID_ORDER": {"xp": 40, "janus_coin": 0},
    "HELIOS_DAILY_PLAY": {"xp": 10, "janus_coin": 0, "daily_cap": 1},
    "CROSS_ORGAN_EXPLORATION": {"xp": 60, "janus_coin": 50, "weekly_cap": 1},
}

ACHIEVEMENTS = {
    "FIRST_FOLLOWER": {"xp": 50, "janus_coin": 50, "badge": "FIRST_FOLLOWER"},
    "GENESIS_BORN": {"xp": 75, "janus_coin": 75, "item": "GENESIS_ORIGIN_SIGIL"},
    "SEVEN_DAYS": {"xp": 100, "janus_coin": 150, "item": "SEVEN_SUN_CHEST"},
    "MIND_MAPPER": {"xp": 50, "janus_coin": 40, "badge": "MIND_MAPPER"},
    "SYNTH_WEAVER": {"xp": 60, "janus_coin": 50, "badge": "SYNTH_WEAVER"},
    "MARKET_SCOUT": {"xp": 75, "janus_coin": 75, "badge": "MARKET_SCOUT"},
    "HELIOS_PILOT": {"xp": 50, "janus_coin": 50, "item": "HELIOS_SOLAR_TOKEN_GAME_ITEM"},
    "COMMUNITY_STREAK_7": {"xp": 120, "janus_coin": 150, "badge": "COMMUNITY_PULSE"},
    "CROSS_ORGAN_5": {"xp": 150, "janus_coin": 200, "item": "JANUS_TRAVELLER_CLOAK"},
    "CONTRIBUTOR": {"xp": 125, "janus_coin": 150, "badge": "BUILDER"},
}


def level_from_xp(total_xp: int) -> int:
    if total_xp < 0:
        raise RewardError("XP_NEGATIVE")
    return min(100, floor(sqrt(total_xp / 100)) + 1)


def daily_claim(*, today: date, last_claim: date | None, current_streak: int) -> dict[str, Any]:
    if last_claim == today:
        raise RewardError("DAILY_ALREADY_CLAIMED")
    if last_claim is not None and last_claim > today:
        raise RewardError("SERVER_DATE_REGRESSION")
    if last_claim == today - timedelta(days=1):
        streak = max(0, int(current_streak)) + 1
    else:
        streak = 1
    cycle_day = ((streak - 1) % 7) + 1
    reward = dict(DAILY_CYCLE[cycle_day])
    return {
        "streak": streak,
        "cycle_day": cycle_day,
        "claimed_for": today.isoformat(),
        "reward": reward,
    }


def _week_key(day: date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def activity_reward(
    *,
    event_type: str,
    event_id: str,
    day: date,
    principal_kind: str,
    seen_event_ids: set[str],
    daily_counts: Mapping[tuple[str, str], int],
    weekly_counts: Mapping[tuple[str, str], int],
    lifetime_counts: Mapping[str, int],
    explicitly_allowed_agent: bool = False,
) -> dict[str, Any]:
    if not event_id:
        raise RewardError("EVENT_ID_REQUIRED")
    if event_id in seen_event_ids:
        raise RewardError("EVENT_ALREADY_REWARDED")
    if principal_kind.upper() in {"BOT", "MACHINE"} and not explicitly_allowed_agent:
        raise RewardError("BOT_ACTIVITY_NOT_REWARDABLE")
    rule = ACTIVITY.get(event_type)
    if rule is None:
        raise RewardError("UNKNOWN_ACTIVITY_TYPE")

    day_key = day.isoformat()
    if "daily_cap" in rule:
        count = int(daily_counts.get((event_type, day_key), 0))
        if count >= int(rule["daily_cap"]):
            return {"rewarded": False, "reason": "DAILY_CAP_REACHED", "event_type": event_type}
    if "weekly_cap" in rule:
        wk = _week_key(day)
        count = int(weekly_counts.get((event_type, wk), 0))
        if count >= int(rule["weekly_cap"]):
            return {"rewarded": False, "reason": "WEEKLY_CAP_REACHED", "event_type": event_type}
    if "lifetime_cap" in rule:
        count = int(lifetime_counts.get(event_type, 0))
        if count >= int(rule["lifetime_cap"]):
            return {"rewarded": False, "reason": "LIFETIME_CAP_REACHED", "event_type": event_type}

    return {
        "rewarded": True,
        "event_type": event_type,
        "event_id": event_id,
        "reward": {"xp": int(rule.get("xp", 0)), "janus_coin": int(rule.get("janus_coin", 0))},
        "counter_keys": {
            "daily": [event_type, day_key] if "daily_cap" in rule else None,
            "weekly": [event_type, _week_key(day)] if "weekly_cap" in rule else None,
            "lifetime": event_type,
        },
    }


def unlock_achievement(*, achievement_id: str, unlocked: set[str]) -> dict[str, Any]:
    if achievement_id not in ACHIEVEMENTS:
        raise RewardError("UNKNOWN_ACHIEVEMENT")
    if achievement_id in unlocked:
        return {"unlocked": False, "reason": "ALREADY_UNLOCKED", "achievement_id": achievement_id}
    return {
        "unlocked": True,
        "achievement_id": achievement_id,
        "reward": dict(ACHIEVEMENTS[achievement_id]),
    }


def apply_reward_snapshot(
    *,
    total_xp: int,
    janus_coin: int,
    reward: Mapping[str, Any],
) -> dict[str, int]:
    xp = int(total_xp) + int(reward.get("xp", 0))
    coin = int(janus_coin) + int(reward.get("janus_coin", 0))
    if xp < 0 or coin < 0:
        raise RewardError("NEGATIVE_LEDGER_RESULT")
    return {"total_xp": xp, "janus_coin": coin, "level": level_from_xp(xp)}
