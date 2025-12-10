-- Ching Tech OS Database Initialization
-- 建立 users 表：記錄曾經登入過的使用者

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- 插入系統說明
COMMENT ON TABLE users IS '使用者表：記錄曾經透過 NAS 認證登入的使用者';
COMMENT ON COLUMN users.username IS 'NAS 帳號';
COMMENT ON COLUMN users.display_name IS '顯示名稱（可選）';
COMMENT ON COLUMN users.created_at IS '首次登入時間';
COMMENT ON COLUMN users.last_login_at IS '最後登入時間';
