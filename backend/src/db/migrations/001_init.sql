CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(100) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  linkedin_url TEXT,
  github_url TEXT,
  kaggle_url TEXT,
  medium_url TEXT,
  profile_photo TEXT,
  role_title VARCHAR(150),
  bio TEXT,
  skills TEXT[],
  profile_completed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS teams (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  team_name VARCHAR(150) NOT NULL,
  team_code VARCHAR(12) UNIQUE NOT NULL,
  description TEXT,
  created_by UUID REFERENCES profiles(id),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS team_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  role VARCHAR(20) CHECK (role IN ('leader','member')) NOT NULL,
  joined_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(team_id, user_id)
);

CREATE TABLE IF NOT EXISTS reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES profiles(id),
  team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
  project_name VARCHAR(200),
  work_done TEXT,
  outcome TEXT,
  blockers TEXT,
  pending_work TEXT,
  chatbot_summary TEXT,
  report_date DATE NOT NULL,
  submitted_time TIMESTAMPTZ DEFAULT now(),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS discussions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  leader_id UUID REFERENCES profiles(id),
  team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
  project_name VARCHAR(200),
  discussion_summary TEXT,
  report_date DATE NOT NULL,
  submitted_time TIMESTAMPTZ DEFAULT now(),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reports_team_date ON reports(team_id, report_date);
CREATE INDEX IF NOT EXISTS idx_reports_user_date ON reports(user_id, report_date);
CREATE INDEX IF NOT EXISTS idx_discussions_team_date ON discussions(team_id, report_date);
