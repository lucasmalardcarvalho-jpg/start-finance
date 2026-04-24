-- START FINANCE — Supabase setup
-- Run this in the Supabase SQL Editor (https://app.supabase.com → SQL Editor)

-- Users table (mirrors data/users.json)
CREATE TABLE IF NOT EXISTS sf_users (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  email      TEXT UNIQUE NOT NULL,
  password   TEXT NOT NULL,
  avatar     TEXT DEFAULT '🙂',
  color      TEXT DEFAULT '#3B6FF0',
  created_at TEXT
);

-- User financial data table (mirrors userdata/{user_id}.json)
CREATE TABLE IF NOT EXISTS sf_userdata (
  user_id    TEXT PRIMARY KEY,
  data       JSONB NOT NULL DEFAULT '{}',
  updated_at BIGINT DEFAULT 0
);

-- Optional: disable Row Level Security so the service-role key can read/write freely.
-- If you prefer RLS, set up policies allowing the service role full access.
ALTER TABLE sf_users    DISABLE ROW LEVEL SECURITY;
ALTER TABLE sf_userdata DISABLE ROW LEVEL SECURITY;
