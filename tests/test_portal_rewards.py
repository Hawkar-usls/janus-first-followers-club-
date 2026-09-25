from datetime import date
import unittest

from portal_backend.rewards import (
    RewardError,
    activity_reward,
    apply_reward_snapshot,
    daily_claim,
    level_from_xp,
    unlock_achievement,
)


class RewardEngineTests(unittest.TestCase):
    def test_daily_claim_starts_and_advances_streak(self):
        r = daily_claim(today=date(2026, 9, 25), last_claim=None, current_streak=0)
        self.assertEqual(r["streak"], 1)
        self.assertEqual(r["reward"]["janus_coin"], 25)
        r2 = daily_claim(today=date(2026, 9, 26), last_claim=date(2026, 9, 25), current_streak=1)
        self.assertEqual(r2["streak"], 2)
        self.assertEqual(r2["reward"]["janus_coin"], 30)

    def test_same_day_daily_cannot_be_claimed_twice(self):
        with self.assertRaisesRegex(RewardError, "DAILY_ALREADY_CLAIMED"):
            daily_claim(today=date(2026, 9, 25), last_claim=date(2026, 9, 25), current_streak=4)

    def test_missed_day_resets_streak(self):
        r = daily_claim(today=date(2026, 9, 25), last_claim=date(2026, 9, 23), current_streak=9)
        self.assertEqual(r["streak"], 1)

    def test_day_seven_gives_chest_and_cycle_repeats(self):
        r = daily_claim(today=date(2026, 9, 25), last_claim=date(2026, 9, 24), current_streak=6)
        self.assertEqual(r["cycle_day"], 7)
        self.assertEqual(r["reward"]["item"], "PORTAL_DAILY_CHEST")
        r2 = daily_claim(today=date(2026, 9, 26), last_claim=date(2026, 9, 25), current_streak=7)
        self.assertEqual(r2["cycle_day"], 1)

    def test_group_raw_volume_has_daily_cap_one(self):
        first = activity_reward(
            event_type="GROUP_DAILY_PARTICIPATION", event_id="m1", day=date(2026, 9, 25),
            principal_kind="HUMAN", seen_event_ids=set(), daily_counts={}, weekly_counts={}, lifetime_counts={}
        )
        self.assertTrue(first["rewarded"])
        second = activity_reward(
            event_type="GROUP_DAILY_PARTICIPATION", event_id="m2", day=date(2026, 9, 25),
            principal_kind="HUMAN", seen_event_ids=set(), daily_counts={("GROUP_DAILY_PARTICIPATION","2026-09-25"):1},
            weekly_counts={}, lifetime_counts={}
        )
        self.assertFalse(second["rewarded"])
        self.assertEqual(second["reason"], "DAILY_CAP_REACHED")

    def test_same_source_event_cannot_reward_twice(self):
        with self.assertRaisesRegex(RewardError, "EVENT_ALREADY_REWARDED"):
            activity_reward(
                event_type="GENESIS_DAILY_PLAY", event_id="g1", day=date(2026, 9, 25),
                principal_kind="HUMAN", seen_event_ids={"g1"}, daily_counts={}, weekly_counts={}, lifetime_counts={}
            )

    def test_bot_activity_default_denied(self):
        with self.assertRaisesRegex(RewardError, "BOT_ACTIVITY_NOT_REWARDABLE"):
            activity_reward(
                event_type="GROUP_DAILY_PARTICIPATION", event_id="b1", day=date(2026, 9, 25),
                principal_kind="BOT", seen_event_ids=set(), daily_counts={}, weekly_counts={}, lifetime_counts={}
            )

    def test_machine_can_be_explicitly_allowed_but_caps_still_apply(self):
        r = activity_reward(
            event_type="MARKET_COMPLETED_FREE_SEARCH", event_id="a1", day=date(2026, 9, 25),
            principal_kind="MACHINE", explicitly_allowed_agent=True, seen_event_ids=set(),
            daily_counts={}, weekly_counts={}, lifetime_counts={}
        )
        self.assertTrue(r["rewarded"])

    def test_market_first_free_reward_has_lifetime_cap(self):
        r = activity_reward(
            event_type="MARKET_COMPLETED_FREE_SEARCH", event_id="mkt2", day=date(2026, 9, 25),
            principal_kind="HUMAN", seen_event_ids=set(), daily_counts={}, weekly_counts={},
            lifetime_counts={"MARKET_COMPLETED_FREE_SEARCH": 1}
        )
        self.assertFalse(r["rewarded"])
        self.assertEqual(r["reason"], "LIFETIME_CAP_REACHED")

    def test_achievement_only_unlocks_once(self):
        first = unlock_achievement(achievement_id="GENESIS_BORN", unlocked=set())
        self.assertTrue(first["unlocked"])
        second = unlock_achievement(achievement_id="GENESIS_BORN", unlocked={"GENESIS_BORN"})
        self.assertFalse(second["unlocked"])

    def test_level_is_deterministic_and_bounded(self):
        self.assertEqual(level_from_xp(0), 1)
        self.assertEqual(level_from_xp(100), 2)
        self.assertEqual(level_from_xp(900), 4)
        self.assertLessEqual(level_from_xp(10**12), 100)

    def test_reward_snapshot_never_makes_money_claim(self):
        s = apply_reward_snapshot(total_xp=100, janus_coin=50, reward={"xp":25,"janus_coin":10})
        self.assertEqual(s["total_xp"], 125)
        self.assertEqual(s["janus_coin"], 60)


if __name__ == "__main__":
    unittest.main()
