-- 給同事查核用的唯讀帳號。
--
-- 只授 ch001 schema 的 USAGE 與 SELECT，碰不到 public（CTOS 的表不在這個
-- 容器裡，但還是明確限制，免得日後有人往 public 放東西）。
--
-- 執行方式（密碼用環境變數帶入，不寫進檔案）：
--   psql "$DSN" -v pw="'$CH001_READONLY_PASSWORD'" -f readonly.sql

CREATE ROLE ch001_viewer LOGIN PASSWORD :pw;

-- 不能建表、不能建 schema
REVOKE CREATE ON SCHEMA public FROM ch001_viewer;
REVOKE ALL ON DATABASE ch001 FROM PUBLIC;
GRANT CONNECT ON DATABASE ch001 TO ch001_viewer;

GRANT USAGE ON SCHEMA ch001 TO ch001_viewer;
GRANT SELECT ON ALL TABLES IN SCHEMA ch001 TO ch001_viewer;

-- 之後新增的表也自動可讀（分階段匯入，會一直有新表）
ALTER DEFAULT PRIVILEGES IN SCHEMA ch001 GRANT SELECT ON TABLES TO ch001_viewer;

-- 保險：明確擋掉寫入
ALTER ROLE ch001_viewer SET default_transaction_read_only = on;
