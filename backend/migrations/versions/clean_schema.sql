--
-- PostgreSQL database dump
--


-- Dumped from database version 16.11
-- Dumped by pg_dump version 16.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: create_ai_logs_partition(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.create_ai_logs_partition() RETURNS void
    LANGUAGE plpgsql
    AS $$
        DECLARE
            partition_date DATE;
            partition_name TEXT;
            start_date DATE;
            end_date DATE;
        BEGIN
            -- 建立未來兩個月的分區
            FOR i IN 0..1 LOOP
                partition_date := DATE_TRUNC('month', NOW() + (i || ' month')::INTERVAL);
                partition_name := 'ai_logs_' || TO_CHAR(partition_date, 'YYYY_MM');
                start_date := partition_date;
                end_date := partition_date + INTERVAL '1 month';

                -- 檢查分區是否存在
                IF NOT EXISTS (
                    SELECT 1 FROM pg_class
                    WHERE relname = partition_name
                    AND relkind = 'r'
                ) THEN
                    EXECUTE FORMAT(
                        'CREATE TABLE %I PARTITION OF ai_logs FOR VALUES FROM (%L) TO (%L)',
                        partition_name, start_date, end_date
                    );
                    RAISE NOTICE 'Created partition: %', partition_name;
                END IF;
            END LOOP;
        END;
        $$;


--
-- Name: FUNCTION create_ai_logs_partition(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.create_ai_logs_partition() IS '自動建立 ai_logs 分區（當月與下月）';


--
-- Name: create_next_month_partitions(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.create_next_month_partitions() RETURNS void
    LANGUAGE plpgsql
    AS $$
        DECLARE
            next_month_start DATE;
            next_month_end DATE;
            partition_name TEXT;
        BEGIN
            -- 計算下個月的起始和結束日期
            next_month_start := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')::DATE;
            next_month_end := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '2 months')::DATE;

            -- 建立 messages 分區（如果不存在）
            partition_name := 'messages_' || TO_CHAR(next_month_start, 'YYYY_MM');
            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = partition_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF messages FOR VALUES FROM (%L) TO (%L)',
                    partition_name, next_month_start, next_month_end
                );
                RAISE NOTICE 'Created partition: %', partition_name;
            END IF;

            -- 建立 login_records 分區（如果不存在）
            partition_name := 'login_records_' || TO_CHAR(next_month_start, 'YYYY_MM');
            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = partition_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF login_records FOR VALUES FROM (%L) TO (%L)',
                    partition_name, next_month_start, next_month_end
                );
                RAISE NOTICE 'Created partition: %', partition_name;
            END IF;
        END;
        $$;


--
-- Name: FUNCTION create_next_month_partitions(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.create_next_month_partitions() IS '自動建立下個月的分區（messages 和 login_records）';


--
-- Name: drop_old_partitions(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.drop_old_partitions(retention_months integer DEFAULT 12) RETURNS void
    LANGUAGE plpgsql
    AS $_$
        DECLARE
            cutoff_date DATE;
            rec RECORD;
        BEGIN
            cutoff_date := DATE_TRUNC('month', CURRENT_DATE - (retention_months || ' months')::INTERVAL)::DATE;

            -- 刪除過期的 messages 分區
            FOR rec IN
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename ~ '^messages_[0-9]{4}_[0-9]{2}$'
            LOOP
                -- 從分區名稱解析日期
                IF TO_DATE(SUBSTRING(rec.tablename FROM 10), 'YYYY_MM') < cutoff_date THEN
                    EXECUTE format('DROP TABLE IF EXISTS %I', rec.tablename);
                    RAISE NOTICE 'Dropped partition: %', rec.tablename;
                END IF;
            END LOOP;

            -- 刪除過期的 login_records 分區
            FOR rec IN
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename ~ '^login_records_[0-9]{4}_[0-9]{2}$'
            LOOP
                -- 從分區名稱解析日期
                IF TO_DATE(SUBSTRING(rec.tablename FROM 15), 'YYYY_MM') < cutoff_date THEN
                    EXECUTE format('DROP TABLE IF EXISTS %I', rec.tablename);
                    RAISE NOTICE 'Dropped partition: %', rec.tablename;
                END IF;
            END LOOP;
        END;
        $_$;


--
-- Name: FUNCTION drop_old_partitions(retention_months integer); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.drop_old_partitions(retention_months integer) IS '刪除超過保留期限的分區，預設保留 12 個月';


--
-- Name: get_partition_stats(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_partition_stats() RETURNS TABLE(table_name text, partition_name text, row_count bigint, size_bytes bigint)
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RETURN QUERY
            SELECT
                p.parent::TEXT as table_name,
                c.relname::TEXT as partition_name,
                pg_stat_get_live_tuples(c.oid) as row_count,
                pg_total_relation_size(c.oid) as size_bytes
            FROM pg_inherits i
            JOIN pg_class c ON c.oid = i.inhrelid
            JOIN (
                SELECT 'messages'::regclass::oid as parent
                UNION ALL
                SELECT 'login_records'::regclass::oid as parent
            ) p ON p.parent = i.inhparent
            ORDER BY c.relname;
        END;
        $$;


--
-- Name: FUNCTION get_partition_stats(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.get_partition_stats() IS '取得分區統計資訊（列數、大小）';


--
-- Name: update_inventory_current_stock(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_inventory_current_stock() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            -- INSERT 或 UPDATE 時，更新新物料的庫存
            IF (TG_OP = 'INSERT' OR TG_OP = 'UPDATE') THEN
                UPDATE inventory_items
                SET current_stock = (
                    SELECT COALESCE(SUM(CASE WHEN type = 'in' THEN quantity ELSE -quantity END), 0)
                    FROM inventory_transactions
                    WHERE item_id = NEW.item_id
                )
                WHERE id = NEW.item_id;
            END IF;

            -- DELETE 時，或 UPDATE 且 item_id 變更時，更新舊物料的庫存
            IF (TG_OP = 'DELETE' OR (TG_OP = 'UPDATE' AND NEW.item_id <> OLD.item_id)) THEN
                UPDATE inventory_items
                SET current_stock = (
                    SELECT COALESCE(SUM(CASE WHEN type = 'in' THEN quantity ELSE -quantity END), 0)
                    FROM inventory_transactions
                    WHERE item_id = OLD.item_id
                )
                WHERE id = OLD.item_id;
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            ELSE
                RETURN NEW;
            END IF;
        END;
        $$;


--
-- Name: update_inventory_items_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_inventory_items_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$;


--
-- Name: update_inventory_orders_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_inventory_orders_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


--
-- Name: update_tenants_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_tenants_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$;


--
-- Name: update_vendors_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_vendors_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_agents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_agents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(64) NOT NULL,
    display_name character varying(128),
    description text,
    model character varying(32) NOT NULL,
    system_prompt_id uuid,
    is_active boolean DEFAULT true,
    settings jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    tools jsonb DEFAULT '[]'::jsonb,
    tenant_id uuid
);


--
-- Name: TABLE ai_agents; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_agents IS 'AI Agent 設定表';


--
-- Name: COLUMN ai_agents.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_agents.name IS '唯一識別名（如 web-chat-default）';


--
-- Name: COLUMN ai_agents.model; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_agents.model IS 'AI 模型：claude-haiku, claude-sonnet 等';


--
-- Name: COLUMN ai_agents.settings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_agents.settings IS '額外設定 JSON（保留擴展）';


--
-- Name: COLUMN ai_agents.tools; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_agents.tools IS '允許使用的工具列表，如 ["WebSearch", "WebFetch"]';


--
-- Name: COLUMN ai_agents.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_agents.tenant_id IS '租戶 ID（NULL 表示全域 Agent）';


--
-- Name: ai_chats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_chats (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id integer,
    title character varying(100) DEFAULT '新對話'::character varying NOT NULL,
    model character varying(50) DEFAULT 'claude-sonnet'::character varying NOT NULL,
    prompt_name character varying(50) DEFAULT 'default'::character varying NOT NULL,
    messages jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE ai_chats; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_chats IS 'AI 對話記錄表';


--
-- Name: COLUMN ai_chats.id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_chats.id IS '對話 UUID';


--
-- Name: COLUMN ai_chats.user_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_chats.user_id IS '使用者 ID（關聯 users 表）';


--
-- Name: COLUMN ai_chats.title; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_chats.title IS '對話標題';


--
-- Name: COLUMN ai_chats.model; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_chats.model IS 'AI 模型名稱';


--
-- Name: COLUMN ai_chats.prompt_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_chats.prompt_name IS 'System Prompt 名稱（對應 data/prompts/*.md）';


--
-- Name: COLUMN ai_chats.messages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_chats.messages IS '對話訊息 JSONB 陣列 [{role, content, timestamp}]';


--
-- Name: COLUMN ai_chats.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_chats.created_at IS '建立時間';


--
-- Name: COLUMN ai_chats.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_chats.updated_at IS '最後更新時間';


--
-- Name: COLUMN ai_chats.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_chats.tenant_id IS '租戶 ID';


--
-- Name: ai_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    agent_id uuid,
    prompt_id uuid,
    context_type character varying(32),
    context_id character varying(64),
    input_prompt text NOT NULL,
    raw_response text,
    parsed_response jsonb,
    model character varying(32),
    success boolean DEFAULT true,
    error_message text,
    duration_ms integer,
    input_tokens integer,
    output_tokens integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    system_prompt text,
    allowed_tools json,
    tenant_id uuid NOT NULL
)
PARTITION BY RANGE (created_at);


--
-- Name: TABLE ai_logs; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_logs IS 'AI 調用日誌（按月分區）';


--
-- Name: COLUMN ai_logs.context_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_logs.context_type IS '調用情境：web-chat, linebot-group, system, test';


--
-- Name: COLUMN ai_logs.context_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_logs.context_id IS '情境 ID：chat_id, group_id, job_id';


--
-- Name: COLUMN ai_logs.duration_ms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_logs.duration_ms IS 'AI 調用耗時（毫秒）';


--
-- Name: COLUMN ai_logs.system_prompt; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_logs.system_prompt IS '實際使用的 system prompt 內容';


--
-- Name: COLUMN ai_logs.allowed_tools; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_logs.allowed_tools IS '允許使用的工具列表';


--
-- Name: COLUMN ai_logs.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_logs.tenant_id IS '租戶 ID';


--
-- Name: ai_prompts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_prompts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(128) NOT NULL,
    display_name character varying(256),
    category character varying(64),
    content text NOT NULL,
    description text,
    variables jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    tenant_id uuid
);


--
-- Name: TABLE ai_prompts; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_prompts IS 'AI Prompt 管理表';


--
-- Name: COLUMN ai_prompts.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_prompts.name IS '唯一識別名（如 web-chat-default）';


--
-- Name: COLUMN ai_prompts.category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_prompts.category IS '分類：system, task, template';


--
-- Name: COLUMN ai_prompts.variables; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_prompts.variables IS '可用變數說明 JSON';


--
-- Name: COLUMN ai_prompts.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_prompts.tenant_id IS '租戶 ID（NULL 表示全域 Prompt）';


--
-- Name: inventory_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventory_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(200) NOT NULL,
    specification character varying(500),
    unit character varying(50),
    category character varying(100),
    default_vendor character varying(200),
    min_stock numeric(15,3) DEFAULT '0'::numeric,
    current_stock numeric(15,3) DEFAULT '0'::numeric NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by character varying(100),
    default_vendor_id uuid,
    tenant_id uuid NOT NULL,
    model character varying(200),
    storage_location character varying(100)
);


--
-- Name: COLUMN inventory_items.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.name IS '物料名稱';


--
-- Name: COLUMN inventory_items.specification; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.specification IS '規格';


--
-- Name: COLUMN inventory_items.unit; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.unit IS '單位（如：個、台、公斤）';


--
-- Name: COLUMN inventory_items.category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.category IS '類別';


--
-- Name: COLUMN inventory_items.default_vendor; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.default_vendor IS '預設廠商';


--
-- Name: COLUMN inventory_items.min_stock; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.min_stock IS '最低庫存量';


--
-- Name: COLUMN inventory_items.current_stock; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.current_stock IS '目前庫存';


--
-- Name: COLUMN inventory_items.notes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.notes IS '備註';


--
-- Name: COLUMN inventory_items.created_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.created_by IS '建立者';


--
-- Name: COLUMN inventory_items.default_vendor_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.default_vendor_id IS '預設廠商 ID';


--
-- Name: COLUMN inventory_items.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_items.tenant_id IS '租戶 ID';


--
-- Name: inventory_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventory_orders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    item_id uuid NOT NULL,
    order_quantity numeric(15,3) NOT NULL,
    order_date date,
    expected_delivery_date date,
    actual_delivery_date date,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    vendor character varying(200),
    project_id uuid,
    notes text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by character varying(100),
    tenant_id uuid
);


--
-- Name: inventory_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventory_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    item_id uuid NOT NULL,
    type character varying(10) NOT NULL,
    quantity numeric(15,3) NOT NULL,
    transaction_date date DEFAULT CURRENT_DATE NOT NULL,
    vendor character varying(200),
    project_id uuid,
    notes text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by character varying(100),
    tenant_id uuid NOT NULL
);


--
-- Name: COLUMN inventory_transactions.item_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_transactions.item_id IS '物料 ID';


--
-- Name: COLUMN inventory_transactions.type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_transactions.type IS '類型：in（進貨）/ out（出貨）';


--
-- Name: COLUMN inventory_transactions.quantity; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_transactions.quantity IS '數量';


--
-- Name: COLUMN inventory_transactions.transaction_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_transactions.transaction_date IS '進出貨日期';


--
-- Name: COLUMN inventory_transactions.vendor; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_transactions.vendor IS '廠商';


--
-- Name: COLUMN inventory_transactions.project_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_transactions.project_id IS '關聯專案';


--
-- Name: COLUMN inventory_transactions.notes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_transactions.notes IS '備註';


--
-- Name: COLUMN inventory_transactions.created_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_transactions.created_by IS '建立者';


--
-- Name: COLUMN inventory_transactions.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inventory_transactions.tenant_id IS '租戶 ID';


--
-- Name: line_binding_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.line_binding_codes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id integer NOT NULL,
    code character varying(6) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    used_by_line_user_id uuid,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE line_binding_codes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.line_binding_codes IS 'Line 綁定驗證碼';


--
-- Name: COLUMN line_binding_codes.code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_binding_codes.code IS '6 位數字驗證碼';


--
-- Name: COLUMN line_binding_codes.expires_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_binding_codes.expires_at IS '驗證碼過期時間（5 分鐘）';


--
-- Name: COLUMN line_binding_codes.used_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_binding_codes.used_at IS '使用時間';


--
-- Name: COLUMN line_binding_codes.used_by_line_user_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_binding_codes.used_by_line_user_id IS '使用此驗證碼的 Line 用戶';


--
-- Name: COLUMN line_binding_codes.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_binding_codes.tenant_id IS '租戶 ID';


--
-- Name: line_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.line_files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    message_id uuid NOT NULL,
    file_type character varying(32) NOT NULL,
    file_name character varying(512),
    file_size integer,
    mime_type character varying(128),
    nas_path text,
    thumbnail_path text,
    duration integer,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE line_files; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.line_files IS 'Line 檔案記錄';


--
-- Name: COLUMN line_files.file_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_files.file_type IS '檔案類型：image, video, audio, file';


--
-- Name: COLUMN line_files.nas_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_files.nas_path IS 'NAS 儲存路徑';


--
-- Name: COLUMN line_files.duration; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_files.duration IS '音訊/影片長度（毫秒）';


--
-- Name: COLUMN line_files.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_files.tenant_id IS '租戶 ID';


--
-- Name: line_group_memories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.line_group_memories (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    line_group_id uuid NOT NULL,
    title character varying(128) NOT NULL,
    content text NOT NULL,
    is_active boolean DEFAULT true,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE line_group_memories; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.line_group_memories IS 'Line 群組自訂記憶（會加入 AI prompt）';


--
-- Name: COLUMN line_group_memories.title; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_group_memories.title IS '記憶標題（方便識別）';


--
-- Name: COLUMN line_group_memories.content; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_group_memories.content IS '記憶內容（會加入 prompt）';


--
-- Name: COLUMN line_group_memories.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_group_memories.is_active IS '是否啟用';


--
-- Name: COLUMN line_group_memories.created_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_group_memories.created_by IS '建立者（Line 用戶）';


--
-- Name: line_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.line_groups (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    line_group_id character varying(64) NOT NULL,
    name character varying(256),
    picture_url text,
    member_count integer DEFAULT 0,
    project_id uuid,
    is_active boolean DEFAULT true,
    joined_at timestamp with time zone DEFAULT now(),
    left_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    allow_ai_response boolean DEFAULT false,
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE line_groups; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.line_groups IS 'Line 群組資訊';


--
-- Name: COLUMN line_groups.line_group_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_groups.line_group_id IS 'Line 群組 ID';


--
-- Name: COLUMN line_groups.project_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_groups.project_id IS '綁定的專案 ID';


--
-- Name: COLUMN line_groups.allow_ai_response; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_groups.allow_ai_response IS '是否允許 AI 回應（需開啟才會回應）';


--
-- Name: COLUMN line_groups.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_groups.tenant_id IS '租戶 ID';


--
-- Name: line_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.line_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    message_id character varying(64) NOT NULL,
    line_user_id uuid NOT NULL,
    line_group_id uuid,
    message_type character varying(32) NOT NULL,
    content text,
    file_id uuid,
    reply_token character varying(64),
    is_from_bot boolean DEFAULT false,
    ai_processed boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE line_messages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.line_messages IS 'Line 訊息記錄（群組+個人）';


--
-- Name: COLUMN line_messages.line_group_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_messages.line_group_id IS '群組 ID（NULL 表示個人對話）';


--
-- Name: COLUMN line_messages.message_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_messages.message_type IS '訊息類型：text, image, video, audio, file, location, sticker';


--
-- Name: COLUMN line_messages.ai_processed; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_messages.ai_processed IS '是否已經過 AI 處理';


--
-- Name: COLUMN line_messages.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_messages.tenant_id IS '租戶 ID';


--
-- Name: line_user_memories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.line_user_memories (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    line_user_id uuid NOT NULL,
    title character varying(128) NOT NULL,
    content text NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE line_user_memories; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.line_user_memories IS 'Line 個人自訂記憶（會加入 AI prompt）';


--
-- Name: COLUMN line_user_memories.title; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_user_memories.title IS '記憶標題（方便識別）';


--
-- Name: COLUMN line_user_memories.content; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_user_memories.content IS '記憶內容（會加入 prompt）';


--
-- Name: COLUMN line_user_memories.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_user_memories.is_active IS '是否啟用';


--
-- Name: line_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.line_users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    line_user_id character varying(64) NOT NULL,
    display_name character varying(256),
    picture_url text,
    status_message text,
    language character varying(16),
    user_id integer,
    is_friend boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    conversation_reset_at timestamp with time zone,
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE line_users; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.line_users IS 'Line 用戶資訊';


--
-- Name: COLUMN line_users.line_user_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_users.line_user_id IS 'Line 用戶 ID';


--
-- Name: COLUMN line_users.user_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_users.user_id IS '對應的系統用戶 ID';


--
-- Name: COLUMN line_users.conversation_reset_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_users.conversation_reset_at IS '對話重置時間，查詢歷史時只取這個時間之後的訊息';


--
-- Name: COLUMN line_users.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.line_users.tenant_id IS '租戶 ID';


--
-- Name: login_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.login_records (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id integer,
    username character varying(100) NOT NULL,
    success boolean NOT NULL,
    failure_reason character varying(200),
    ip_address inet NOT NULL,
    user_agent text,
    geo_country character varying(100),
    geo_city character varying(100),
    geo_latitude numeric(10,7),
    geo_longitude numeric(10,7),
    device_fingerprint character varying(100),
    device_type character varying(50),
    browser character varying(100),
    os character varying(100),
    session_id character varying(100),
    partition_date date DEFAULT CURRENT_DATE NOT NULL,
    tenant_id uuid NOT NULL
)
PARTITION BY RANGE (partition_date);


--
-- Name: TABLE login_records; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.login_records IS '登入記錄表 - 完整追蹤登入歷史（分區表）';


--
-- Name: COLUMN login_records.success; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.success IS '登入是否成功';


--
-- Name: COLUMN login_records.failure_reason; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.failure_reason IS '失敗原因（如密碼錯誤、帳號不存在等）';


--
-- Name: COLUMN login_records.ip_address; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.ip_address IS '登入 IP 位址';


--
-- Name: COLUMN login_records.user_agent; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.user_agent IS '瀏覽器 User-Agent';


--
-- Name: COLUMN login_records.geo_country; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.geo_country IS 'GeoIP 解析的國家';


--
-- Name: COLUMN login_records.geo_city; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.geo_city IS 'GeoIP 解析的城市';


--
-- Name: COLUMN login_records.geo_latitude; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.geo_latitude IS 'GeoIP 解析的緯度';


--
-- Name: COLUMN login_records.geo_longitude; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.geo_longitude IS 'GeoIP 解析的經度';


--
-- Name: COLUMN login_records.device_fingerprint; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.device_fingerprint IS '裝置指紋 hash';


--
-- Name: COLUMN login_records.device_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.device_type IS '裝置類型: desktop/mobile/tablet';


--
-- Name: COLUMN login_records.browser; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.browser IS '瀏覽器名稱與版本';


--
-- Name: COLUMN login_records.os; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.os IS '作業系統名稱與版本';


--
-- Name: COLUMN login_records.partition_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.partition_date IS '分區鍵（日期）';


--
-- Name: COLUMN login_records.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.login_records.tenant_id IS '租戶 ID';


--
-- Name: login_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.login_records_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: login_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.login_records_id_seq OWNED BY public.login_records.id;


--
-- Name: messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    severity character varying(20) NOT NULL,
    source character varying(20) NOT NULL,
    category character varying(50),
    title character varying(200) NOT NULL,
    content text,
    metadata jsonb,
    user_id integer,
    session_id character varying(100),
    is_read boolean DEFAULT false,
    partition_date date DEFAULT CURRENT_DATE NOT NULL,
    tenant_id uuid NOT NULL,
    CONSTRAINT chk_messages_severity CHECK (((severity)::text = ANY (ARRAY[('debug'::character varying)::text, ('info'::character varying)::text, ('warning'::character varying)::text, ('error'::character varying)::text, ('critical'::character varying)::text]))),
    CONSTRAINT chk_messages_source CHECK (((source)::text = ANY (ARRAY[('system'::character varying)::text, ('security'::character varying)::text, ('app'::character varying)::text, ('user'::character varying)::text])))
)
PARTITION BY RANGE (partition_date);


--
-- Name: TABLE messages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.messages IS '訊息中心 - 訊息表（分區表）';


--
-- Name: COLUMN messages.severity; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.messages.severity IS '嚴重程度: debug/info/warning/error/critical';


--
-- Name: COLUMN messages.source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.messages.source IS '來源: system/security/app/user';


--
-- Name: COLUMN messages.category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.messages.category IS '細分類: auth/file-manager/ai-assistant 等';


--
-- Name: COLUMN messages.metadata; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.messages.metadata IS '結構化附加資料 (JSONB)';


--
-- Name: COLUMN messages.is_read; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.messages.is_read IS '是否已讀';


--
-- Name: COLUMN messages.partition_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.messages.partition_date IS '分區鍵（日期）';


--
-- Name: COLUMN messages.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.messages.tenant_id IS '租戶 ID';


--
-- Name: messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.messages_id_seq OWNED BY public.messages.id;


--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id integer NOT NULL,
    token character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    used_at timestamp with time zone
);


--
-- Name: TABLE password_reset_tokens; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.password_reset_tokens IS '密碼重設 Token';


--
-- Name: COLUMN password_reset_tokens.token; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.password_reset_tokens.token IS '重設 token（隨機字串）';


--
-- Name: COLUMN password_reset_tokens.expires_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.password_reset_tokens.expires_at IS '過期時間';


--
-- Name: COLUMN password_reset_tokens.used_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.password_reset_tokens.used_at IS '使用時間（已使用則不為 NULL）';


--
-- Name: project_attachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_attachments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    filename character varying(500) NOT NULL,
    file_type character varying(50),
    file_size bigint,
    storage_path character varying(1000) NOT NULL,
    description text,
    uploaded_at timestamp without time zone DEFAULT now(),
    uploaded_by character varying(100),
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE project_attachments; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.project_attachments IS '專案附件';


--
-- Name: COLUMN project_attachments.file_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_attachments.file_type IS '檔案類型：image, pdf, cad, document, other';


--
-- Name: COLUMN project_attachments.storage_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_attachments.storage_path IS '儲存路徑：本機路徑或 nas://...';


--
-- Name: COLUMN project_attachments.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_attachments.tenant_id IS '租戶 ID';


--
-- Name: project_delivery_schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_delivery_schedules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    vendor character varying(200) NOT NULL,
    item character varying(500) NOT NULL,
    quantity character varying(100),
    order_date date,
    expected_delivery_date date,
    actual_delivery_date date,
    status character varying(50) DEFAULT 'pending'::character varying,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by character varying(100),
    vendor_id uuid,
    item_id uuid,
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE project_delivery_schedules; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.project_delivery_schedules IS '專案發包/交貨期程';


--
-- Name: COLUMN project_delivery_schedules.vendor; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_delivery_schedules.vendor IS '廠商名稱';


--
-- Name: COLUMN project_delivery_schedules.item; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_delivery_schedules.item IS '料件名稱';


--
-- Name: COLUMN project_delivery_schedules.quantity; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_delivery_schedules.quantity IS '數量（含單位，如「2 台」）';


--
-- Name: COLUMN project_delivery_schedules.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_delivery_schedules.status IS '狀態：pending(待發包), ordered(已發包), delivered(已到貨), completed(已完成)';


--
-- Name: COLUMN project_delivery_schedules.vendor_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_delivery_schedules.vendor_id IS '關聯廠商 ID';


--
-- Name: COLUMN project_delivery_schedules.item_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_delivery_schedules.item_id IS '關聯物料 ID';


--
-- Name: COLUMN project_delivery_schedules.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_delivery_schedules.tenant_id IS '租戶 ID';


--
-- Name: project_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_links (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    title character varying(200) NOT NULL,
    url character varying(2000) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE project_links; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.project_links IS '專案連結（NAS 路徑或外部 URL）';


--
-- Name: COLUMN project_links.url; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_links.url IS 'NAS 路徑 (/) 或外部 URL (https://)';


--
-- Name: COLUMN project_links.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_links.tenant_id IS '租戶 ID';


--
-- Name: project_meetings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_meetings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    title character varying(200) NOT NULL,
    meeting_date timestamp with time zone NOT NULL,
    location character varying(200),
    attendees text[],
    content text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by character varying(100),
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE project_meetings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.project_meetings IS '專案會議記錄';


--
-- Name: COLUMN project_meetings.attendees; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_meetings.attendees IS '參與人員名單';


--
-- Name: COLUMN project_meetings.content; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_meetings.content IS 'Markdown 格式會議內容';


--
-- Name: COLUMN project_meetings.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_meetings.tenant_id IS '租戶 ID';


--
-- Name: project_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_members (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    role character varying(100),
    company character varying(200),
    email character varying(200),
    phone character varying(50),
    notes text,
    is_internal boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    user_id integer,
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE project_members; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.project_members IS '專案成員/聯絡人';


--
-- Name: COLUMN project_members.role; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_members.role IS '角色：PM, 工程師, 客戶等';


--
-- Name: COLUMN project_members.is_internal; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_members.is_internal IS '是否為內部人員';


--
-- Name: COLUMN project_members.user_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_members.user_id IS '關聯的 CTOS 用戶 ID，用於權限控制';


--
-- Name: COLUMN project_members.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_members.tenant_id IS '租戶 ID';


--
-- Name: project_milestones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_milestones (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    milestone_type character varying(50) DEFAULT 'custom'::character varying,
    planned_date date,
    actual_date date,
    status character varying(50) DEFAULT 'pending'::character varying,
    notes text,
    sort_order integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE project_milestones; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.project_milestones IS '專案里程碑';


--
-- Name: COLUMN project_milestones.milestone_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_milestones.milestone_type IS '里程碑類型：design, manufacture, delivery, field_test, acceptance, custom';


--
-- Name: COLUMN project_milestones.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_milestones.status IS '狀態：pending, in_progress, completed, delayed';


--
-- Name: COLUMN project_milestones.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_milestones.tenant_id IS '租戶 ID';


--
-- Name: projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.projects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(200) NOT NULL,
    description text,
    status character varying(50) DEFAULT 'active'::character varying,
    start_date date,
    end_date date,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by character varying(100),
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE projects; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.projects IS '專案主表';


--
-- Name: COLUMN projects.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.status IS '專案狀態：active, completed, on_hold, cancelled';


--
-- Name: COLUMN projects.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.tenant_id IS '租戶 ID';


--
-- Name: public_share_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.public_share_links (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    token character varying(10) NOT NULL,
    resource_type character varying(20) NOT NULL,
    resource_id character varying(100) NOT NULL,
    created_by character varying(100) NOT NULL,
    expires_at timestamp with time zone,
    access_count integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL
);


--
-- Name: TABLE public_share_links; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.public_share_links IS '公開分享連結';


--
-- Name: COLUMN public_share_links.token; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.public_share_links.token IS '短 token 用於 URL，6 字元';


--
-- Name: COLUMN public_share_links.resource_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.public_share_links.resource_type IS '資源類型：knowledge 或 project';


--
-- Name: COLUMN public_share_links.resource_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.public_share_links.resource_id IS '資源 ID（kb-xxx 或專案 UUID）';


--
-- Name: COLUMN public_share_links.created_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.public_share_links.created_by IS '建立者使用者名稱';


--
-- Name: COLUMN public_share_links.expires_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.public_share_links.expires_at IS '過期時間，NULL 表示永久有效';


--
-- Name: COLUMN public_share_links.access_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.public_share_links.access_count IS '存取次數統計';


--
-- Name: COLUMN public_share_links.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.public_share_links.tenant_id IS '租戶 ID';


--
-- Name: tenant_admins; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_admins (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    role character varying(50) DEFAULT 'admin'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    user_id integer NOT NULL
);


--
-- Name: COLUMN tenant_admins.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenant_admins.tenant_id IS '租戶 ID';


--
-- Name: COLUMN tenant_admins.role; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenant_admins.role IS '角色：admin, owner';


--
-- Name: COLUMN tenant_admins.user_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenant_admins.user_id IS '用戶 ID';


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(200) NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    plan character varying(50) DEFAULT 'trial'::character varying NOT NULL,
    settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    storage_quota_mb bigint DEFAULT '5120'::bigint NOT NULL,
    storage_used_mb bigint DEFAULT '0'::bigint NOT NULL,
    trial_ends_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: COLUMN tenants.code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.code IS '租戶代碼（用於登入識別）';


--
-- Name: COLUMN tenants.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.name IS '租戶名稱';


--
-- Name: COLUMN tenants.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.status IS '狀態：active, suspended, trial';


--
-- Name: COLUMN tenants.plan; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.plan IS '方案：trial, basic, pro, enterprise';


--
-- Name: COLUMN tenants.settings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.settings IS '租戶設定';


--
-- Name: COLUMN tenants.storage_quota_mb; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.storage_quota_mb IS '儲存配額 (MB)';


--
-- Name: COLUMN tenants.storage_used_mb; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.storage_used_mb IS '已使用儲存 (MB)';


--
-- Name: COLUMN tenants.trial_ends_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.trial_ends_at IS '試用期結束時間';


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(100) NOT NULL,
    display_name character varying(100),
    preferences jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    last_login_at timestamp without time zone,
    tenant_id uuid NOT NULL,
    role character varying(50) DEFAULT 'user'::character varying NOT NULL,
    password_hash character varying(255),
    email character varying(255),
    password_changed_at timestamp with time zone,
    must_change_password boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: TABLE users; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.users IS '使用者表：記錄曾經透過 NAS 認證登入的使用者';


--
-- Name: COLUMN users.username; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.username IS 'NAS 帳號';


--
-- Name: COLUMN users.display_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.display_name IS '顯示名稱（可選）';


--
-- Name: COLUMN users.preferences; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.preferences IS '使用者偏好設定（JSONB），包含 theme 等設定';


--
-- Name: COLUMN users.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.created_at IS '首次登入時間';


--
-- Name: COLUMN users.last_login_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.last_login_at IS '最後登入時間';


--
-- Name: COLUMN users.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.tenant_id IS '租戶 ID';


--
-- Name: COLUMN users.role; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.role IS '角色：user, tenant_admin, platform_admin';


--
-- Name: COLUMN users.password_hash; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.password_hash IS 'bcrypt 密碼雜湊';


--
-- Name: COLUMN users.email; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.email IS '使用者 Email（可選）';


--
-- Name: COLUMN users.password_changed_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.password_changed_at IS '密碼最後更改時間';


--
-- Name: COLUMN users.must_change_password; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.must_change_password IS '下次登入需更改密碼';


--
-- Name: COLUMN users.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.is_active IS '帳號是否啟用';


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: vendors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendors (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    erp_code character varying(50),
    name character varying(200) NOT NULL,
    short_name character varying(100),
    contact_person character varying(100),
    phone character varying(50),
    fax character varying(50),
    email character varying(200),
    address text,
    tax_id character varying(20),
    payment_terms character varying(200),
    notes text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by character varying(100),
    tenant_id uuid NOT NULL
);


--
-- Name: COLUMN vendors.erp_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.erp_code IS 'ERP 系統廠商編號';


--
-- Name: COLUMN vendors.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.name IS '廠商名稱';


--
-- Name: COLUMN vendors.short_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.short_name IS '簡稱';


--
-- Name: COLUMN vendors.contact_person; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.contact_person IS '聯絡人';


--
-- Name: COLUMN vendors.phone; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.phone IS '電話';


--
-- Name: COLUMN vendors.fax; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.fax IS '傳真';


--
-- Name: COLUMN vendors.email; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.email IS 'Email';


--
-- Name: COLUMN vendors.address; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.address IS '地址';


--
-- Name: COLUMN vendors.tax_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.tax_id IS '統一編號';


--
-- Name: COLUMN vendors.payment_terms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.payment_terms IS '付款條件';


--
-- Name: COLUMN vendors.notes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.notes IS '備註';


--
-- Name: COLUMN vendors.is_active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.is_active IS '是否啟用';


--
-- Name: COLUMN vendors.created_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.created_by IS '建立者';


--
-- Name: COLUMN vendors.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.tenant_id IS '租戶 ID';


--
-- Name: login_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records ALTER COLUMN id SET DEFAULT nextval('public.login_records_id_seq'::regclass);


--
-- Name: messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages ALTER COLUMN id SET DEFAULT nextval('public.messages_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: ai_agents ai_agents_name_tenant_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_agents
    ADD CONSTRAINT ai_agents_name_tenant_id_key UNIQUE (name, tenant_id);


--
-- Name: ai_agents ai_agents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_agents
    ADD CONSTRAINT ai_agents_pkey PRIMARY KEY (id);


--
-- Name: ai_chats ai_chats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_chats
    ADD CONSTRAINT ai_chats_pkey PRIMARY KEY (id);


--
-- Name: ai_logs ai_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_logs
    ADD CONSTRAINT ai_logs_pkey PRIMARY KEY (id, created_at);


--
-- Name: ai_prompts ai_prompts_name_tenant_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_prompts
    ADD CONSTRAINT ai_prompts_name_tenant_id_key UNIQUE (name, tenant_id);


--
-- Name: ai_prompts ai_prompts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_prompts
    ADD CONSTRAINT ai_prompts_pkey PRIMARY KEY (id);


--
-- Name: inventory_items inventory_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_items
    ADD CONSTRAINT inventory_items_pkey PRIMARY KEY (id);


--
-- Name: inventory_orders inventory_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_orders
    ADD CONSTRAINT inventory_orders_pkey PRIMARY KEY (id);


--
-- Name: inventory_transactions inventory_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_transactions
    ADD CONSTRAINT inventory_transactions_pkey PRIMARY KEY (id);


--
-- Name: line_binding_codes line_binding_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_binding_codes
    ADD CONSTRAINT line_binding_codes_pkey PRIMARY KEY (id);


--
-- Name: line_files line_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_files
    ADD CONSTRAINT line_files_pkey PRIMARY KEY (id);


--
-- Name: line_group_memories line_group_memories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_group_memories
    ADD CONSTRAINT line_group_memories_pkey PRIMARY KEY (id);


--
-- Name: line_groups line_groups_line_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_groups
    ADD CONSTRAINT line_groups_line_group_id_key UNIQUE (line_group_id);


--
-- Name: line_groups line_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_groups
    ADD CONSTRAINT line_groups_pkey PRIMARY KEY (id);


--
-- Name: line_messages line_messages_message_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_messages
    ADD CONSTRAINT line_messages_message_id_key UNIQUE (message_id);


--
-- Name: line_messages line_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_messages
    ADD CONSTRAINT line_messages_pkey PRIMARY KEY (id);


--
-- Name: line_user_memories line_user_memories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_user_memories
    ADD CONSTRAINT line_user_memories_pkey PRIMARY KEY (id);


--
-- Name: line_users line_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_users
    ADD CONSTRAINT line_users_pkey PRIMARY KEY (id);


--
-- Name: login_records login_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records
    ADD CONSTRAINT login_records_pkey PRIMARY KEY (id, partition_date);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id, partition_date);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_token_key UNIQUE (token);


--
-- Name: project_attachments project_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_attachments
    ADD CONSTRAINT project_attachments_pkey PRIMARY KEY (id);


--
-- Name: project_delivery_schedules project_delivery_schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_delivery_schedules
    ADD CONSTRAINT project_delivery_schedules_pkey PRIMARY KEY (id);


--
-- Name: project_links project_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_links
    ADD CONSTRAINT project_links_pkey PRIMARY KEY (id);


--
-- Name: project_meetings project_meetings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_meetings
    ADD CONSTRAINT project_meetings_pkey PRIMARY KEY (id);


--
-- Name: project_members project_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_pkey PRIMARY KEY (id);


--
-- Name: project_milestones project_milestones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_milestones
    ADD CONSTRAINT project_milestones_pkey PRIMARY KEY (id);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: public_share_links public_share_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_share_links
    ADD CONSTRAINT public_share_links_pkey PRIMARY KEY (id);


--
-- Name: public_share_links public_share_links_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_share_links
    ADD CONSTRAINT public_share_links_token_key UNIQUE (token);


--
-- Name: tenant_admins tenant_admins_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_admins
    ADD CONSTRAINT tenant_admins_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_code_key UNIQUE (code);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: vendors vendors_erp_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_erp_code_key UNIQUE (erp_code);


--
-- Name: vendors vendors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_pkey PRIMARY KEY (id);


--
-- Name: idx_ai_agents_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_agents_is_active ON public.ai_agents USING btree (is_active);


--
-- Name: idx_ai_agents_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_agents_name ON public.ai_agents USING btree (name);


--
-- Name: idx_ai_agents_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_agents_tenant_id ON public.ai_agents USING btree (tenant_id);


--
-- Name: idx_ai_chats_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_chats_tenant_id ON public.ai_chats USING btree (tenant_id);


--
-- Name: idx_ai_chats_tenant_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_chats_tenant_user ON public.ai_chats USING btree (tenant_id, user_id);


--
-- Name: idx_ai_chats_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_chats_updated_at ON public.ai_chats USING btree (updated_at DESC);


--
-- Name: idx_ai_chats_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_chats_user_id ON public.ai_chats USING btree (user_id);


--
-- Name: idx_ai_logs_agent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_agent_id ON ONLY public.ai_logs USING btree (agent_id);


--
-- Name: idx_ai_logs_context; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_context ON ONLY public.ai_logs USING btree (context_type, context_id);


--
-- Name: idx_ai_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_created_at ON ONLY public.ai_logs USING btree (created_at DESC);


--
-- Name: idx_ai_logs_success; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_success ON ONLY public.ai_logs USING btree (success);


--
-- Name: idx_ai_logs_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_tenant_created ON ONLY public.ai_logs USING btree (tenant_id, created_at);


--
-- Name: idx_ai_logs_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_tenant_id ON ONLY public.ai_logs USING btree (tenant_id);


--
-- Name: idx_ai_prompts_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_prompts_category ON public.ai_prompts USING btree (category);


--
-- Name: idx_ai_prompts_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_prompts_name ON public.ai_prompts USING btree (name);


--
-- Name: idx_ai_prompts_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_prompts_tenant_id ON public.ai_prompts USING btree (tenant_id);


--
-- Name: idx_binding_codes_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_binding_codes_code ON public.line_binding_codes USING btree (code);


--
-- Name: idx_binding_codes_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_binding_codes_user_id ON public.line_binding_codes USING btree (user_id);


--
-- Name: idx_delivery_schedules_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_delivery_schedules_item_id ON public.project_delivery_schedules USING btree (item_id);


--
-- Name: idx_delivery_schedules_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_delivery_schedules_project_id ON public.project_delivery_schedules USING btree (project_id);


--
-- Name: idx_delivery_schedules_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_delivery_schedules_status ON public.project_delivery_schedules USING btree (status);


--
-- Name: idx_delivery_schedules_vendor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_delivery_schedules_vendor ON public.project_delivery_schedules USING btree (vendor);


--
-- Name: idx_delivery_schedules_vendor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_delivery_schedules_vendor_id ON public.project_delivery_schedules USING btree (vendor_id);


--
-- Name: idx_inventory_items_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_items_category ON public.inventory_items USING btree (category);


--
-- Name: idx_inventory_items_default_vendor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_items_default_vendor_id ON public.inventory_items USING btree (default_vendor_id);


--
-- Name: idx_inventory_items_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_items_tenant_id ON public.inventory_items USING btree (tenant_id);


--
-- Name: idx_inventory_items_tenant_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_inventory_items_tenant_name ON public.inventory_items USING btree (tenant_id, name);


--
-- Name: idx_inventory_orders_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_orders_item_id ON public.inventory_orders USING btree (item_id);


--
-- Name: idx_inventory_orders_order_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_orders_order_date ON public.inventory_orders USING btree (order_date);


--
-- Name: idx_inventory_orders_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_orders_project_id ON public.inventory_orders USING btree (project_id);


--
-- Name: idx_inventory_orders_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_orders_status ON public.inventory_orders USING btree (status);


--
-- Name: idx_inventory_orders_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_orders_tenant_id ON public.inventory_orders USING btree (tenant_id);


--
-- Name: idx_inventory_transactions_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_transactions_date ON public.inventory_transactions USING btree (transaction_date);


--
-- Name: idx_inventory_transactions_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_transactions_item_id ON public.inventory_transactions USING btree (item_id);


--
-- Name: idx_inventory_transactions_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_transactions_project_id ON public.inventory_transactions USING btree (project_id);


--
-- Name: idx_inventory_transactions_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_transactions_tenant_id ON public.inventory_transactions USING btree (tenant_id);


--
-- Name: idx_inventory_transactions_tenant_item; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_transactions_tenant_item ON public.inventory_transactions USING btree (tenant_id, item_id);


--
-- Name: idx_inventory_transactions_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_transactions_type ON public.inventory_transactions USING btree (type);


--
-- Name: idx_line_binding_codes_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_binding_codes_tenant_id ON public.line_binding_codes USING btree (tenant_id);


--
-- Name: idx_line_files_file_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_files_file_type ON public.line_files USING btree (file_type);


--
-- Name: idx_line_files_message_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_files_message_id ON public.line_files USING btree (message_id);


--
-- Name: idx_line_files_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_files_tenant_id ON public.line_files USING btree (tenant_id);


--
-- Name: idx_line_group_memories_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_group_memories_active ON public.line_group_memories USING btree (line_group_id, is_active);


--
-- Name: idx_line_group_memories_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_group_memories_group_id ON public.line_group_memories USING btree (line_group_id);


--
-- Name: idx_line_groups_line_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_groups_line_group_id ON public.line_groups USING btree (line_group_id);


--
-- Name: idx_line_groups_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_groups_project_id ON public.line_groups USING btree (project_id);


--
-- Name: idx_line_groups_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_groups_tenant_id ON public.line_groups USING btree (tenant_id);


--
-- Name: idx_line_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_messages_created_at ON public.line_messages USING btree (created_at DESC);


--
-- Name: idx_line_messages_line_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_messages_line_group_id ON public.line_messages USING btree (line_group_id);


--
-- Name: idx_line_messages_line_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_messages_line_user_id ON public.line_messages USING btree (line_user_id);


--
-- Name: idx_line_messages_message_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_messages_message_type ON public.line_messages USING btree (message_type);


--
-- Name: idx_line_messages_tenant_group; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_messages_tenant_group ON public.line_messages USING btree (tenant_id, line_group_id);


--
-- Name: idx_line_messages_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_messages_tenant_id ON public.line_messages USING btree (tenant_id);


--
-- Name: idx_line_user_memories_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_user_memories_active ON public.line_user_memories USING btree (line_user_id, is_active);


--
-- Name: idx_line_user_memories_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_user_memories_user_id ON public.line_user_memories USING btree (line_user_id);


--
-- Name: idx_line_users_line_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_users_line_user_id ON public.line_users USING btree (line_user_id);


--
-- Name: idx_line_users_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_users_tenant_id ON public.line_users USING btree (tenant_id);


--
-- Name: idx_line_users_tenant_line_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_users_tenant_line_user ON public.line_users USING btree (tenant_id, line_user_id);


--
-- Name: idx_line_users_tenant_line_user_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_line_users_tenant_line_user_unique ON public.line_users USING btree (tenant_id, line_user_id);


--
-- Name: idx_line_users_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_users_user_id ON public.line_users USING btree (user_id);


--
-- Name: idx_login_records_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_records_created_at ON ONLY public.login_records USING btree (created_at DESC);


--
-- Name: idx_login_records_device_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_records_device_fingerprint ON ONLY public.login_records USING btree (device_fingerprint);


--
-- Name: idx_login_records_ip_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_records_ip_address ON ONLY public.login_records USING btree (ip_address);


--
-- Name: idx_login_records_success; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_records_success ON ONLY public.login_records USING btree (success);


--
-- Name: idx_login_records_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_records_tenant_id ON ONLY public.login_records USING btree (tenant_id);


--
-- Name: idx_login_records_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_records_user_id ON ONLY public.login_records USING btree (user_id);


--
-- Name: idx_login_records_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_records_username ON ONLY public.login_records USING btree (username);


--
-- Name: idx_messages_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_messages_category ON ONLY public.messages USING btree (category);


--
-- Name: idx_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_messages_created_at ON ONLY public.messages USING btree (created_at DESC);


--
-- Name: idx_messages_is_read; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_messages_is_read ON ONLY public.messages USING btree (is_read) WHERE (is_read = false);


--
-- Name: idx_messages_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_messages_severity ON ONLY public.messages USING btree (severity);


--
-- Name: idx_messages_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_messages_source ON ONLY public.messages USING btree (source);


--
-- Name: idx_messages_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_messages_tenant_created ON ONLY public.messages USING btree (tenant_id, created_at);


--
-- Name: idx_messages_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_messages_tenant_id ON ONLY public.messages USING btree (tenant_id);


--
-- Name: idx_messages_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_messages_user_id ON ONLY public.messages USING btree (user_id);


--
-- Name: idx_password_reset_tokens_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_password_reset_tokens_expires_at ON public.password_reset_tokens USING btree (expires_at);


--
-- Name: idx_password_reset_tokens_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_password_reset_tokens_token ON public.password_reset_tokens USING btree (token);


--
-- Name: idx_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: idx_project_attachments_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_attachments_project_id ON public.project_attachments USING btree (project_id);


--
-- Name: idx_project_attachments_tenant_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_attachments_tenant_project ON public.project_attachments USING btree (tenant_id, project_id);


--
-- Name: idx_project_delivery_schedules_tenant_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_delivery_schedules_tenant_project ON public.project_delivery_schedules USING btree (tenant_id, project_id);


--
-- Name: idx_project_links_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_links_project_id ON public.project_links USING btree (project_id);


--
-- Name: idx_project_links_tenant_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_links_tenant_project ON public.project_links USING btree (tenant_id, project_id);


--
-- Name: idx_project_meetings_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_meetings_date ON public.project_meetings USING btree (meeting_date DESC);


--
-- Name: idx_project_meetings_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_meetings_project_id ON public.project_meetings USING btree (project_id);


--
-- Name: idx_project_meetings_tenant_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_meetings_tenant_project ON public.project_meetings USING btree (tenant_id, project_id);


--
-- Name: idx_project_members_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_members_project_id ON public.project_members USING btree (project_id);


--
-- Name: idx_project_members_tenant_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_members_tenant_project ON public.project_members USING btree (tenant_id, project_id);


--
-- Name: idx_project_members_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_members_user_id ON public.project_members USING btree (user_id);


--
-- Name: idx_project_milestones_planned_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_milestones_planned_date ON public.project_milestones USING btree (planned_date);


--
-- Name: idx_project_milestones_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_milestones_project_id ON public.project_milestones USING btree (project_id);


--
-- Name: idx_project_milestones_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_milestones_status ON public.project_milestones USING btree (status);


--
-- Name: idx_project_milestones_tenant_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_milestones_tenant_project ON public.project_milestones USING btree (tenant_id, project_id);


--
-- Name: idx_projects_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_created_at ON public.projects USING btree (created_at DESC);


--
-- Name: idx_projects_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_status ON public.projects USING btree (status);


--
-- Name: idx_projects_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_tenant_id ON public.projects USING btree (tenant_id);


--
-- Name: idx_projects_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_tenant_status ON public.projects USING btree (tenant_id, status);


--
-- Name: idx_public_share_links_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_public_share_links_tenant_id ON public.public_share_links USING btree (tenant_id);


--
-- Name: idx_share_links_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_share_links_created_by ON public.public_share_links USING btree (created_by);


--
-- Name: idx_share_links_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_share_links_expires_at ON public.public_share_links USING btree (expires_at);


--
-- Name: idx_share_links_resource; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_share_links_resource ON public.public_share_links USING btree (resource_type, resource_id);


--
-- Name: idx_share_links_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_share_links_token ON public.public_share_links USING btree (token);


--
-- Name: idx_tenant_admins_tenant_user; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_tenant_admins_tenant_user ON public.tenant_admins USING btree (tenant_id, user_id);


--
-- Name: idx_tenants_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_tenants_code ON public.tenants USING btree (code);


--
-- Name: idx_tenants_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenants_status ON public.tenants USING btree (status);


--
-- Name: idx_users_tenant_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_users_tenant_email ON public.users USING btree (tenant_id, email) WHERE (email IS NOT NULL);


--
-- Name: idx_users_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_tenant_id ON public.users USING btree (tenant_id);


--
-- Name: idx_users_tenant_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_users_tenant_username ON public.users USING btree (tenant_id, username);


--
-- Name: idx_users_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_username ON public.users USING btree (username);


--
-- Name: idx_vendors_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendors_is_active ON public.vendors USING btree (is_active);


--
-- Name: idx_vendors_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendors_name ON public.vendors USING btree (name);


--
-- Name: idx_vendors_tenant_erp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendors_tenant_erp_code ON public.vendors USING btree (tenant_id, erp_code);


--
-- Name: idx_vendors_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendors_tenant_id ON public.vendors USING btree (tenant_id);


--
-- Name: inventory_items trigger_inventory_items_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_inventory_items_updated_at BEFORE UPDATE ON public.inventory_items FOR EACH ROW EXECUTE FUNCTION public.update_inventory_items_updated_at();


--
-- Name: inventory_orders trigger_inventory_orders_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_inventory_orders_updated_at BEFORE UPDATE ON public.inventory_orders FOR EACH ROW EXECUTE FUNCTION public.update_inventory_orders_updated_at();


--
-- Name: tenants trigger_tenants_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_tenants_updated_at BEFORE UPDATE ON public.tenants FOR EACH ROW EXECUTE FUNCTION public.update_tenants_updated_at();


--
-- Name: inventory_transactions trigger_update_inventory_stock; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_update_inventory_stock AFTER INSERT OR DELETE OR UPDATE ON public.inventory_transactions FOR EACH ROW EXECUTE FUNCTION public.update_inventory_current_stock();


--
-- Name: vendors trigger_vendors_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_vendors_updated_at BEFORE UPDATE ON public.vendors FOR EACH ROW EXECUTE FUNCTION public.update_vendors_updated_at();


--
-- Name: ai_agents ai_agents_system_prompt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_agents
    ADD CONSTRAINT ai_agents_system_prompt_id_fkey FOREIGN KEY (system_prompt_id) REFERENCES public.ai_prompts(id) ON DELETE SET NULL;


--
-- Name: ai_chats ai_chats_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_chats
    ADD CONSTRAINT ai_chats_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ai_logs ai_logs_agent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.ai_logs
    ADD CONSTRAINT ai_logs_agent_id_fkey FOREIGN KEY (agent_id) REFERENCES public.ai_agents(id) ON DELETE SET NULL;


--
-- Name: ai_logs ai_logs_prompt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.ai_logs
    ADD CONSTRAINT ai_logs_prompt_id_fkey FOREIGN KEY (prompt_id) REFERENCES public.ai_prompts(id) ON DELETE SET NULL;


--
-- Name: ai_agents fk_ai_agents_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_agents
    ADD CONSTRAINT fk_ai_agents_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: ai_chats fk_ai_chats_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_chats
    ADD CONSTRAINT fk_ai_chats_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: ai_prompts fk_ai_prompts_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_prompts
    ADD CONSTRAINT fk_ai_prompts_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: project_delivery_schedules fk_delivery_schedules_item; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_delivery_schedules
    ADD CONSTRAINT fk_delivery_schedules_item FOREIGN KEY (item_id) REFERENCES public.inventory_items(id) ON DELETE SET NULL;


--
-- Name: project_delivery_schedules fk_delivery_schedules_vendor; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_delivery_schedules
    ADD CONSTRAINT fk_delivery_schedules_vendor FOREIGN KEY (vendor_id) REFERENCES public.vendors(id) ON DELETE SET NULL;


--
-- Name: inventory_items fk_inventory_items_default_vendor; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_items
    ADD CONSTRAINT fk_inventory_items_default_vendor FOREIGN KEY (default_vendor_id) REFERENCES public.vendors(id) ON DELETE SET NULL;


--
-- Name: inventory_items fk_inventory_items_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_items
    ADD CONSTRAINT fk_inventory_items_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: inventory_transactions fk_inventory_transactions_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_transactions
    ADD CONSTRAINT fk_inventory_transactions_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: line_binding_codes fk_line_binding_codes_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_binding_codes
    ADD CONSTRAINT fk_line_binding_codes_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: line_files fk_line_files_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_files
    ADD CONSTRAINT fk_line_files_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: line_groups fk_line_groups_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_groups
    ADD CONSTRAINT fk_line_groups_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: line_messages fk_line_messages_file_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_messages
    ADD CONSTRAINT fk_line_messages_file_id FOREIGN KEY (file_id) REFERENCES public.line_files(id) ON DELETE SET NULL;


--
-- Name: line_messages fk_line_messages_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_messages
    ADD CONSTRAINT fk_line_messages_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: line_users fk_line_users_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_users
    ADD CONSTRAINT fk_line_users_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: project_attachments fk_project_attachments_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_attachments
    ADD CONSTRAINT fk_project_attachments_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: project_delivery_schedules fk_project_delivery_schedules_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_delivery_schedules
    ADD CONSTRAINT fk_project_delivery_schedules_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: project_links fk_project_links_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_links
    ADD CONSTRAINT fk_project_links_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: project_meetings fk_project_meetings_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_meetings
    ADD CONSTRAINT fk_project_meetings_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: project_members fk_project_members_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT fk_project_members_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: project_milestones fk_project_milestones_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_milestones
    ADD CONSTRAINT fk_project_milestones_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: projects fk_projects_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT fk_projects_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: public_share_links fk_public_share_links_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_share_links
    ADD CONSTRAINT fk_public_share_links_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: users fk_users_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: vendors fk_vendors_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT fk_vendors_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: inventory_orders inventory_orders_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_orders
    ADD CONSTRAINT inventory_orders_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.inventory_items(id) ON DELETE CASCADE;


--
-- Name: inventory_orders inventory_orders_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_orders
    ADD CONSTRAINT inventory_orders_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE SET NULL;


--
-- Name: inventory_orders inventory_orders_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_orders
    ADD CONSTRAINT inventory_orders_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: inventory_transactions inventory_transactions_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_transactions
    ADD CONSTRAINT inventory_transactions_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.inventory_items(id) ON DELETE CASCADE;


--
-- Name: inventory_transactions inventory_transactions_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_transactions
    ADD CONSTRAINT inventory_transactions_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE SET NULL;


--
-- Name: line_binding_codes line_binding_codes_used_by_line_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_binding_codes
    ADD CONSTRAINT line_binding_codes_used_by_line_user_id_fkey FOREIGN KEY (used_by_line_user_id) REFERENCES public.line_users(id) ON DELETE SET NULL;


--
-- Name: line_binding_codes line_binding_codes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_binding_codes
    ADD CONSTRAINT line_binding_codes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: line_files line_files_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_files
    ADD CONSTRAINT line_files_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.line_messages(id) ON DELETE CASCADE;


--
-- Name: line_group_memories line_group_memories_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_group_memories
    ADD CONSTRAINT line_group_memories_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.line_users(id) ON DELETE SET NULL;


--
-- Name: line_group_memories line_group_memories_line_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_group_memories
    ADD CONSTRAINT line_group_memories_line_group_id_fkey FOREIGN KEY (line_group_id) REFERENCES public.line_groups(id) ON DELETE CASCADE;


--
-- Name: line_groups line_groups_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_groups
    ADD CONSTRAINT line_groups_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE SET NULL;


--
-- Name: line_messages line_messages_line_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_messages
    ADD CONSTRAINT line_messages_line_group_id_fkey FOREIGN KEY (line_group_id) REFERENCES public.line_groups(id) ON DELETE CASCADE;


--
-- Name: line_messages line_messages_line_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_messages
    ADD CONSTRAINT line_messages_line_user_id_fkey FOREIGN KEY (line_user_id) REFERENCES public.line_users(id) ON DELETE CASCADE;


--
-- Name: line_user_memories line_user_memories_line_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_user_memories
    ADD CONSTRAINT line_user_memories_line_user_id_fkey FOREIGN KEY (line_user_id) REFERENCES public.line_users(id) ON DELETE CASCADE;


--
-- Name: line_users line_users_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.line_users
    ADD CONSTRAINT line_users_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: login_records login_records_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.login_records
    ADD CONSTRAINT login_records_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: messages messages_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.messages
    ADD CONSTRAINT messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: project_attachments project_attachments_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_attachments
    ADD CONSTRAINT project_attachments_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_delivery_schedules project_delivery_schedules_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_delivery_schedules
    ADD CONSTRAINT project_delivery_schedules_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_links project_links_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_links
    ADD CONSTRAINT project_links_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_meetings project_meetings_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_meetings
    ADD CONSTRAINT project_meetings_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_members project_members_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_members project_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: project_milestones project_milestones_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_milestones
    ADD CONSTRAINT project_milestones_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: tenant_admins tenant_admins_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_admins
    ADD CONSTRAINT tenant_admins_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenant_admins tenant_admins_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_admins
    ADD CONSTRAINT tenant_admins_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


