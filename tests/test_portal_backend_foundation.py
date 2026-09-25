import hashlib
import hmac
import json
import sqlite3
import unittest
from urllib.parse import urlencode

from portal_backend.telegram_auth import TelegramAuthError, validate_mini_app_init_data


def make_init_data(*, token: str, auth_date: int, user: dict) -> str:
    fields = {
        "auth_date": str(auth_date),
        "query_id": "AAE-test",
        "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False),
    }
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class PortalBackendFoundationTests(unittest.TestCase):
    def test_schema_constraints_and_uniqueness(self):
        db=sqlite3.connect(":memory:")
        db.executescript(open("portal_backend/schema.sql",encoding="utf-8").read())
        db.execute("INSERT INTO accounts(account_id,display_name,created_at) VALUES(?,?,?)",("a1","User","2026-09-25T00:00:00Z"))
        db.execute("INSERT INTO balances(account_id,asset,available,reserved,updated_at) VALUES(?,?,?,?,?)",("a1","JANUS_COIN",0,0,"2026-09-25T00:00:00Z"))
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("UPDATE balances SET available=-1 WHERE account_id='a1' AND asset='JANUS_COIN'")
        db.execute("INSERT INTO principals(provider,provider_subject,account_id,verified_at) VALUES(?,?,?,?)",("telegram","42","a1","2026-09-25T00:00:00Z"))
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("INSERT INTO principals(provider,provider_subject,account_id,verified_at) VALUES(?,?,?,?)",("telegram","42","a1","2026-09-25T00:00:00Z"))
        db.execute("INSERT INTO reward_events(source_event_id,account_id,source,event_type,source_receipt_digest,reward_json,occurred_at,rewarded_at) VALUES(?,?,?,?,?,?,?,?)",("evt1","a1","GROUP","GROUP_DAILY_PARTICIPATION","sha256:x","{}","2026-09-25T00:00:00Z","2026-09-25T00:00:01Z"))
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("INSERT INTO reward_events(source_event_id,account_id,source,event_type,source_receipt_digest,reward_json,occurred_at,rewarded_at) VALUES(?,?,?,?,?,?,?,?)",("evt1","a1","GROUP","GROUP_DAILY_PARTICIPATION","sha256:y","{}","2026-09-25T00:00:02Z","2026-09-25T00:00:03Z"))

    def test_valid_telegram_mini_app_identity(self):
        token="123456:ABCDEF"
        raw=make_init_data(token=token,auth_date=1_790_000_000,user={"id":987654321,"first_name":"Alex","username":"hawk","is_bot":False})
        ident=validate_mini_app_init_data(raw,bot_token=token,now=1_790_000_100,max_age_seconds=600)
        self.assertEqual(ident.user_id,"987654321")
        self.assertEqual(ident.display_name,"Alex")
        self.assertEqual(ident.username,"hawk")

    def test_tampered_or_expired_telegram_identity_fails(self):
        token="123456:ABCDEF"
        raw=make_init_data(token=token,auth_date=1_790_000_000,user={"id":987654321,"first_name":"Alex","is_bot":False})
        with self.assertRaisesRegex(TelegramAuthError,"HASH_INVALID"):
            validate_mini_app_init_data(raw.replace("Alex","Mallory"),bot_token=token,now=1_790_000_100)
        with self.assertRaisesRegex(TelegramAuthError,"EXPIRED"):
            validate_mini_app_init_data(raw,bot_token=token,now=1_790_010_000,max_age_seconds=600)

    def test_bot_cannot_login_as_human_account(self):
        token="123456:ABCDEF"
        raw=make_init_data(token=token,auth_date=1_790_000_000,user={"id":999,"first_name":"Bot","is_bot":True})
        with self.assertRaisesRegex(TelegramAuthError,"BOT_CANNOT_LOGIN"):
            validate_mini_app_init_data(raw,bot_token=token,now=1_790_000_100)


if __name__ == "__main__":
    unittest.main()
