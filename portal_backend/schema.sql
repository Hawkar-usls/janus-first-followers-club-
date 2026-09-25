PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS accounts (
  account_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS principals (
  provider TEXT NOT NULL,
  provider_subject TEXT NOT NULL,
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  verified_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (provider, provider_subject)
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id_hash TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  csrf_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS balances (
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  asset TEXT NOT NULL,
  available INTEGER NOT NULL DEFAULT 0 CHECK (available >= 0),
  reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (account_id, asset)
);

CREATE TABLE IF NOT EXISTS balance_ledger (
  entry_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  asset TEXT NOT NULL,
  delta_available INTEGER NOT NULL DEFAULT 0,
  delta_reserved INTEGER NOT NULL DEFAULT 0,
  reason TEXT NOT NULL,
  source_receipt_digest TEXT,
  idempotency_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  namespace TEXT NOT NULL,
  item_id TEXT NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (account_id, namespace, item_id)
);

CREATE TABLE IF NOT EXISTS inventory_ledger (
  entry_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  namespace TEXT NOT NULL,
  item_id TEXT NOT NULL,
  delta_quantity INTEGER NOT NULL,
  reason TEXT NOT NULL,
  source_receipt_digest TEXT,
  idempotency_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS progression (
  account_id TEXT PRIMARY KEY REFERENCES accounts(account_id) ON DELETE CASCADE,
  xp INTEGER NOT NULL DEFAULT 0 CHECK (xp >= 0),
  level INTEGER NOT NULL DEFAULT 1 CHECK (level >= 1),
  daily_streak INTEGER NOT NULL DEFAULT 0 CHECK (daily_streak >= 0),
  last_daily_claim_utc_date TEXT,
  total_daily_claims INTEGER NOT NULL DEFAULT 0 CHECK (total_daily_claims >= 0),
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reward_events (
  source_event_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  event_type TEXT NOT NULL,
  source_receipt_digest TEXT NOT NULL,
  reward_json TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  rewarded_at TEXT NOT NULL,
  reversed_by_entry_id TEXT
);

CREATE TABLE IF NOT EXISTS achievements (
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  achievement_id TEXT NOT NULL,
  reward_receipt_id TEXT NOT NULL UNIQUE,
  unlocked_at TEXT NOT NULL,
  PRIMARY KEY (account_id, achievement_id)
);

CREATE TABLE IF NOT EXISTS genesis_state (
  account_id TEXT PRIMARY KEY REFERENCES accounts(account_id) ON DELETE CASCADE,
  session_id TEXT,
  world_id TEXT,
  turn INTEGER NOT NULL DEFAULT 0 CHECK (turn >= 0),
  current_location TEXT,
  portable_save_digest TEXT,
  state_json TEXT NOT NULL DEFAULT '{}',
  revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS graph_state (
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  organ TEXT NOT NULL CHECK (organ IN ('HRAIN','INAIHR')),
  graph_id TEXT,
  revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
  state_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (account_id, organ)
);

CREATE TABLE IF NOT EXISTS helios_state (
  account_id TEXT PRIMARY KEY REFERENCES accounts(account_id) ON DELETE CASCADE,
  profile_id TEXT,
  spin_energy INTEGER NOT NULL DEFAULT 0 CHECK (spin_energy >= 0),
  state_json TEXT NOT NULL DEFAULT '{}',
  revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_links (
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  market_principal_id TEXT NOT NULL,
  verified_at TEXT NOT NULL,
  first_free_search_consumed INTEGER NOT NULL DEFAULT 0 CHECK (first_free_search_consumed IN (0,1)),
  PRIMARY KEY (account_id, market_principal_id)
);

CREATE TABLE IF NOT EXISTS organ_receipts (
  receipt_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  organ TEXT NOT NULL,
  kind TEXT NOT NULL,
  digest TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency (
  idempotency_key TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  route TEXT NOT NULL,
  request_digest TEXT NOT NULL,
  response_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reward_events_account ON reward_events(account_id, rewarded_at);
CREATE INDEX IF NOT EXISTS idx_ledger_account ON balance_ledger(account_id, created_at);
CREATE INDEX IF NOT EXISTS idx_inventory_ledger_account ON inventory_ledger(account_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id, expires_at);
