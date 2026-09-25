from datetime import date
import sqlite3
import unittest

from portal_backend.service import (
    PortalStoreError,
    account_snapshot,
    claim_daily,
    create_or_get_account,
    init_db,
    record_activity_reward,
)


class PortalServiceTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        init_db(self.db)
        self.account=create_or_get_account(
            self.db,provider="telegram",provider_subject="42",
            display_name="Alex",now_iso="2026-09-25T01:00:00Z",account_id="acct-1"
        )

    def test_account_creation_is_principal_idempotent(self):
        same=create_or_get_account(
            self.db,provider="telegram",provider_subject="42",
            display_name="Different",now_iso="2026-09-25T02:00:00Z"
        )
        self.assertFalse(same["created"])
        self.assertEqual(same["account_id"],"acct-1")

    def test_daily_claim_updates_coin_xp_streak_and_replays_idempotently(self):
        first=claim_daily(self.db,account_id="acct-1",today_utc=date(2026,9,25),idempotency_key="d-1",now_iso="2026-09-25T03:00:00Z")
        self.assertEqual(first["reward"]["janus_coin"],25)
        snap=account_snapshot(self.db,"acct-1")
        self.assertEqual(snap["balances"]["JANUS_COIN"]["available"],25)
        self.assertEqual(snap["progression"]["daily"]["streak"],1)
        replay=claim_daily(self.db,account_id="acct-1",today_utc=date(2026,9,25),idempotency_key="d-1",now_iso="2026-09-25T03:01:00Z")
        self.assertEqual(replay,first)
        snap2=account_snapshot(self.db,"acct-1")
        self.assertEqual(snap2["balances"]["JANUS_COIN"]["available"],25)

    def test_second_daily_with_different_key_same_day_fails(self):
        claim_daily(self.db,account_id="acct-1",today_utc=date(2026,9,25),idempotency_key="d-1",now_iso="2026-09-25T03:00:00Z")
        with self.assertRaisesRegex(ValueError,"DAILY_ALREADY_CLAIMED"):
            claim_daily(self.db,account_id="acct-1",today_utc=date(2026,9,25),idempotency_key="d-2",now_iso="2026-09-25T03:02:00Z")

    def test_activity_reward_is_event_unique_and_idempotent(self):
        r=record_activity_reward(
            self.db,account_id="acct-1",source_event_id="tg-msg-1",source="GROUP_TELEGRAM",
            event_type="GROUP_DAILY_PARTICIPATION",source_receipt_digest="sha256:abc",
            occurred_at="2026-09-25T04:00:00Z",reward={"xp":15,"janus_coin":10},
            idempotency_key="r-1",now_iso="2026-09-25T04:00:01Z"
        )
        self.assertTrue(r["ok"])
        replay=record_activity_reward(
            self.db,account_id="acct-1",source_event_id="tg-msg-1",source="GROUP_TELEGRAM",
            event_type="GROUP_DAILY_PARTICIPATION",source_receipt_digest="sha256:abc",
            occurred_at="2026-09-25T04:00:00Z",reward={"xp":15,"janus_coin":10},
            idempotency_key="r-1",now_iso="2026-09-25T04:00:02Z"
        )
        self.assertEqual(replay,r)
        with self.assertRaisesRegex(PortalStoreError,"SOURCE_EVENT_ALREADY_REWARDED"):
            record_activity_reward(
                self.db,account_id="acct-1",source_event_id="tg-msg-1",source="GROUP_TELEGRAM",
                event_type="GROUP_DAILY_PARTICIPATION",source_receipt_digest="sha256:abc",
                occurred_at="2026-09-25T04:00:00Z",reward={"xp":15,"janus_coin":10},
                idempotency_key="r-2",now_iso="2026-09-25T04:00:03Z"
            )

    def test_item_reward_is_persisted(self):
        record_activity_reward(
            self.db,account_id="acct-1",source_event_id="ach-1",source="PORTAL",
            event_type="ACHIEVEMENT",source_receipt_digest="sha256:item",
            occurred_at="2026-09-25T05:00:00Z",reward={"xp":100,"janus_coin":50,"item":"SEVEN_SUN_CHEST"},
            idempotency_key="item-1",now_iso="2026-09-25T05:00:01Z"
        )
        snap=account_snapshot(self.db,"acct-1")
        self.assertEqual(snap["inventory"][0]["item_id"],"SEVEN_SUN_CHEST")
        self.assertEqual(snap["inventory"][0]["quantity"],1)


if __name__=="__main__":
    unittest.main()
