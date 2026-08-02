-- wrangler d1 execute carsite --file=workers/d1_schema.sql
CREATE TABLE IF NOT EXISTS subscribers(
  email TEXT PRIMARY KEY,
  token TEXT,
  confirmed INTEGER DEFAULT 0,
  created TEXT
);
