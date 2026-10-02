ALTER TABLE reports
  ADD COLUMN IF NOT EXISTS leader_work    TEXT,
  ADD COLUMN IF NOT EXISTS team_progress  TEXT,
  ADD COLUMN IF NOT EXISTS next_plan      TEXT;
