-- Add per-user settings JSONB column for personal configuration (e.g. K-line MA).
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{}'::jsonb;
