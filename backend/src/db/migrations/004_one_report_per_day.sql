-- One report per user/team/day and one discussion per leader/team/day.
-- Existing same-day duplicates are collapsed to the most recently submitted row.

ALTER TABLE reports     ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE discussions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

DELETE FROM reports r
USING (
  SELECT id, ROW_NUMBER() OVER (
    PARTITION BY user_id, team_id, report_date
    ORDER BY submitted_time DESC, created_at DESC, id DESC
  ) AS rn
  FROM reports
) d
WHERE r.id = d.id AND d.rn > 1;

DELETE FROM discussions x
USING (
  SELECT id, ROW_NUMBER() OVER (
    PARTITION BY leader_id, team_id, report_date
    ORDER BY submitted_time DESC, created_at DESC, id DESC
  ) AS rn
  FROM discussions
) d
WHERE x.id = d.id AND d.rn > 1;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'reports_user_team_date_key') THEN
    ALTER TABLE reports
      ADD CONSTRAINT reports_user_team_date_key UNIQUE (user_id, team_id, report_date);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'discussions_leader_team_date_key') THEN
    ALTER TABLE discussions
      ADD CONSTRAINT discussions_leader_team_date_key UNIQUE (leader_id, team_id, report_date);
  END IF;
END $$;
