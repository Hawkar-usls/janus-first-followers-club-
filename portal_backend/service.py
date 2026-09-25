from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import date
from typing import Any, Mapping

from portal_backend.rewards import apply_reward_snapshot, daily_claim, level_from_xp


class PortalStoreError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def init_db(db: sqlite3.Connection, schema_path: str = "portal_backend/schema.sql") -> None:
    db.execute("PRAGMA foreign_keys = ON")
    with open(schema_path, encoding="utf-8") as fh:
        db.executescript(fh.read())


def _account_exists(db: sqlite3.Connection, account_id: str) -> bool:
    return db.execute("SELECT 1 FROM accounts WHERE account_id=?", (account_id,)).fetchone() is not None


def create_or_get_account(
    db: sqlite3.Connection,
    *,
    provider: str,
    provider_subject: str,
    display_name: str,
    now_iso: str,
    account_id: str | None = None,
) -> dict[str, Any]:
    row = db.execute(
        "SELECT a.account_id,a.display_name FROM principals p JOIN accounts a ON a.account_id=p.account_id "
        "WHERE p.provider=? AND p.provider_subject=?",
        (provider, provider_subject),
    ).fetchone()
    if row:
        return {"account_id": row[0], "display_name": row[1], "created": False}

    aid = account_id or str(uuid.uuid4())
    try:
        with db:
            db.execute(
                "INSERT INTO accounts(account_id,display_name,created_at) VALUES(?,?,?)",
                (aid, display_name[:120], now_iso),
            )
            db.execute(
                "INSERT INTO principals(provider,provider_subject,account_id,verified_at) VALUES(?,?,?,?)",
                (provider, provider_subject, aid, now_iso),
            )
            db.execute(
                "INSERT INTO balances(account_id,asset,available,reserved,updated_at) VALUES(?,?,?,?,?)",
                (aid, "JANUS_COIN", 0, 0, now_iso),
            )
            db.execute(
                "INSERT INTO progression(account_id,xp,level,daily_streak,total_daily_claims,updated_at) VALUES(?,?,?,?,?,?)",
                (aid, 0, 1, 0, 0, now_iso),
            )
    except sqlite3.IntegrityError as exc:
        raise PortalStoreError("ACCOUNT_CREATE_CONFLICT") from exc
    return {"account_id": aid, "display_name": display_name[:120], "created": True}


def _load_idempotent(db: sqlite3.Connection, key: str, account_id: str, route: str) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT response_json FROM idempotency WHERE idempotency_key=? AND account_id=? AND route=?",
        (key, account_id, route),
    ).fetchone()
    return json.loads(row[0]) if row else None


def _save_idempotent(
    db: sqlite3.Connection,
    *,
    key: str,
    account_id: str,
    route: str,
    request_digest: str,
    response: Mapping[str, Any],
    now_iso: str,
) -> None:
    db.execute(
        "INSERT INTO idempotency(idempotency_key,account_id,route,request_digest,response_json,created_at) "
        "VALUES(?,?,?,?,?,?)",
        (key, account_id, route, request_digest, _json(response), now_iso),
    )


def _ensure_balance_row(db: sqlite3.Connection, account_id: str, now_iso: str) -> None:
    db.execute(
        "INSERT OR IGNORE INTO balances(account_id,asset,available,reserved,updated_at) VALUES(?,?,?,?,?)",
        (account_id, "JANUS_COIN", 0, 0, now_iso),
    )


def _apply_reward(
    db: sqlite3.Connection,
    *,
    account_id: str,
    reward: Mapping[str, Any],
    reason: str,
    receipt_digest: str,
    ledger_idempotency_key: str,
    now_iso: str,
) -> dict[str, Any]:
    _ensure_balance_row(db, account_id, now_iso)
    bal = db.execute(
        "SELECT available FROM balances WHERE account_id=? AND asset='JANUS_COIN'",
        (account_id,),
    ).fetchone()
    prog = db.execute(
        "SELECT xp FROM progression WHERE account_id=?",
        (account_id,),
    ).fetchone()
    current_coin = int(bal[0] if bal else 0)
    current_xp = int(prog[0] if prog else 0)
    new = apply_reward_snapshot(
        total_xp=current_xp,
        janus_coin=current_coin,
        reward=reward,
    )
    coin_delta = int(reward.get("janus_coin", 0))
    xp_delta = int(reward.get("xp", 0))
    if coin_delta:
        entry_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO balance_ledger(entry_id,account_id,asset,delta_available,delta_reserved,reason,"
            "source_receipt_digest,idempotency_key,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (entry_id, account_id, "JANUS_COIN", coin_delta, 0, reason, receipt_digest, ledger_idempotency_key, now_iso),
        )
        db.execute(
            "UPDATE balances SET available=?,updated_at=? WHERE account_id=? AND asset='JANUS_COIN'",
            (new["janus_coin"], now_iso, account_id),
        )
    db.execute(
        "UPDATE progression SET xp=?,level=?,updated_at=? WHERE account_id=?",
        (new["total_xp"], new["level"], now_iso, account_id),
    )
    item = reward.get("item")
    if item:
        namespace = "PORTAL"
        inv_key = f"{ledger_idempotency_key}:item"
        db.execute(
            "INSERT INTO inventory_ledger(entry_id,account_id,namespace,item_id,delta_quantity,reason,"
            "source_receipt_digest,idempotency_key,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), account_id, namespace, str(item), 1, reason, receipt_digest, inv_key, now_iso),
        )
        db.execute(
            "INSERT INTO inventory(account_id,namespace,item_id,quantity,revision,updated_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(account_id,namespace,item_id) DO UPDATE SET "
            "quantity=inventory.quantity+1,revision=inventory.revision+1,updated_at=excluded.updated_at",
            (account_id, namespace, str(item), 1, 1, now_iso),
        )
    return {
        "janus_coin": new["janus_coin"],
        "xp": new["total_xp"],
        "level": new["level"],
        "reward": dict(reward),
    }


def record_activity_reward(
    db: sqlite3.Connection,
    *,
    account_id: str,
    source_event_id: str,
    source: str,
    event_type: str,
    source_receipt_digest: str,
    occurred_at: str,
    reward: Mapping[str, Any],
    idempotency_key: str,
    now_iso: str,
) -> dict[str, Any]:
    if not _account_exists(db, account_id):
        raise PortalStoreError("ACCOUNT_NOT_FOUND")
    if not source_event_id or not source_receipt_digest or not idempotency_key:
        raise PortalStoreError("REWARD_BINDING_REQUIRED")
    route = "activity-reward"
    request_digest = hashlib.sha256(_json({
        "source_event_id": source_event_id,
        "event_type": event_type,
        "source_receipt_digest": source_receipt_digest,
        "reward": reward,
    }).encode()).hexdigest()
    prior = _load_idempotent(db, idempotency_key, account_id, route)
    if prior is not None:
        return prior
    if db.execute("SELECT 1 FROM reward_events WHERE source_event_id=?", (source_event_id,)).fetchone():
        raise PortalStoreError("SOURCE_EVENT_ALREADY_REWARDED")

    with db:
        result = _apply_reward(
            db,
            account_id=account_id,
            reward=reward,
            reason=f"ACTIVITY:{event_type}",
            receipt_digest=source_receipt_digest,
            ledger_idempotency_key=f"{idempotency_key}:balance",
            now_iso=now_iso,
        )
        db.execute(
            "INSERT INTO reward_events(source_event_id,account_id,source,event_type,source_receipt_digest,"
            "reward_json,occurred_at,rewarded_at) VALUES(?,?,?,?,?,?,?,?)",
            (source_event_id, account_id, source, event_type, source_receipt_digest, _json(reward), occurred_at, now_iso),
        )
        response = {"ok": True, "source_event_id": source_event_id, **result}
        _save_idempotent(
            db,key=idempotency_key,account_id=account_id,route=route,
            request_digest=request_digest,response=response,now_iso=now_iso,
        )
    return response


def claim_daily(
    db: sqlite3.Connection,
    *,
    account_id: str,
    today_utc: date,
    idempotency_key: str,
    now_iso: str,
) -> dict[str, Any]:
    if not _account_exists(db, account_id):
        raise PortalStoreError("ACCOUNT_NOT_FOUND")
    if not idempotency_key:
        raise PortalStoreError("IDEMPOTENCY_KEY_REQUIRED")
    route = "daily-claim"
    prior = _load_idempotent(db, idempotency_key, account_id, route)
    if prior is not None:
        return prior
    row = db.execute(
        "SELECT daily_streak,last_daily_claim_utc_date,total_daily_claims FROM progression WHERE account_id=?",
        (account_id,),
    ).fetchone()
    if not row:
        raise PortalStoreError("PROGRESSION_NOT_FOUND")
    last = date.fromisoformat(row[1]) if row[1] else None
    decision = daily_claim(today=today_utc,last_claim=last,current_streak=int(row[0]))
    receipt_digest = "sha256:" + hashlib.sha256(
        f"daily:{account_id}:{today_utc.isoformat()}".encode()
    ).hexdigest()
    with db:
        result = _apply_reward(
            db,account_id=account_id,reward=decision["reward"],
            reason=f"DAILY:{today_utc.isoformat()}",receipt_digest=receipt_digest,
            ledger_idempotency_key=f"{idempotency_key}:balance",now_iso=now_iso,
        )
        db.execute(
            "UPDATE progression SET daily_streak=?,last_daily_claim_utc_date=?,"
            "total_daily_claims=total_daily_claims+1,updated_at=? WHERE account_id=?",
            (decision["streak"],today_utc.isoformat(),now_iso,account_id),
        )
        response={"ok":True,**decision,**result}
        _save_idempotent(
            db,key=idempotency_key,account_id=account_id,route=route,
            request_digest=receipt_digest,response=response,now_iso=now_iso,
        )
    return response


def account_snapshot(db: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    a=db.execute("SELECT account_id,display_name,created_at,status FROM accounts WHERE account_id=?",(account_id,)).fetchone()
    if not a:
        raise PortalStoreError("ACCOUNT_NOT_FOUND")
    bal=db.execute("SELECT available,reserved FROM balances WHERE account_id=? AND asset='JANUS_COIN'",(account_id,)).fetchone() or (0,0)
    p=db.execute("SELECT xp,level,daily_streak,last_daily_claim_utc_date,total_daily_claims FROM progression WHERE account_id=?",(account_id,)).fetchone() or (0,1,0,None,0)
    items=[
        {"namespace":r[0],"item_id":r[1],"quantity":r[2],"revision":r[3]}
        for r in db.execute("SELECT namespace,item_id,quantity,revision FROM inventory WHERE account_id=? AND quantity>0 ORDER BY namespace,item_id",(account_id,))
    ]
    achievements=[r[0] for r in db.execute("SELECT achievement_id FROM achievements WHERE account_id=? ORDER BY unlocked_at",(account_id,))]
    return {
        "account_id":a[0],
        "display_name":a[1],
        "created_at":a[2],
        "status":a[3],
        "balances":{"JANUS_COIN":{"available":int(bal[0]),"reserved":int(bal[1])}},
        "inventory":items,
        "progression":{
            "xp":int(p[0]),"level":int(p[1]),
            "daily":{"streak":int(p[2]),"last_claim_utc_date":p[3],"total_claims":int(p[4])},
            "achievements":achievements,
        },
    }
