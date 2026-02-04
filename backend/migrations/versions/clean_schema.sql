--
-- PostgreSQL database dump
--

\restrict B3zAt31VAvJjuvFyyx5hiB89dSnTRde1vhoLIujIBB41QJw9GGoHdACrXbvMykE

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
-- Name: ai_logs_2025_12; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_logs_2025_12 (
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
);


--
-- Name: ai_logs_2026_01; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_logs_2026_01 (
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
);


--
-- Name: ai_logs_2026_02; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_logs_2026_02 (
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
);


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
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: bot_binding_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_binding_codes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id integer NOT NULL,
    code character varying(6) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    used_by_bot_user_id uuid,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL,
    platform_type character varying(20) DEFAULT 'line'::character varying NOT NULL
);


--
-- Name: bot_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_files (
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
    tenant_id uuid NOT NULL,
    platform_type character varying(20) DEFAULT 'line'::character varying NOT NULL
);


--
-- Name: bot_group_memories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_group_memories (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bot_group_id uuid NOT NULL,
    title character varying(128) NOT NULL,
    content text NOT NULL,
    is_active boolean DEFAULT true,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: bot_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_groups (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    platform_group_id character varying(64) NOT NULL,
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
    tenant_id uuid NOT NULL,
    platform_type character varying(20) DEFAULT 'line'::character varying NOT NULL
);


--
-- Name: bot_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    message_id character varying(64) NOT NULL,
    bot_user_id uuid NOT NULL,
    bot_group_id uuid,
    message_type character varying(32) NOT NULL,
    content text,
    file_id uuid,
    reply_token character varying(64),
    is_from_bot boolean DEFAULT false,
    ai_processed boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL,
    platform_type character varying(20) DEFAULT 'line'::character varying NOT NULL
);


--
-- Name: bot_user_memories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_user_memories (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bot_user_id uuid NOT NULL,
    title character varying(128) NOT NULL,
    content text NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: bot_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    platform_user_id character varying(64) NOT NULL,
    display_name character varying(256),
    picture_url text,
    status_message text,
    language character varying(16),
    user_id integer,
    is_friend boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    conversation_reset_at timestamp with time zone,
    tenant_id uuid NOT NULL,
    platform_type character varying(20) DEFAULT 'line'::character varying NOT NULL
);


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
-- Name: login_records_2026_01; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.login_records_2026_01 (
    id bigint DEFAULT nextval('public.login_records_id_seq'::regclass) NOT NULL,
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
);


--
-- Name: login_records_2026_02; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.login_records_2026_02 (
    id bigint DEFAULT nextval('public.login_records_id_seq'::regclass) NOT NULL,
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
);


--
-- Name: login_records_2026_03; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.login_records_2026_03 (
    id bigint DEFAULT nextval('public.login_records_id_seq'::regclass) NOT NULL,
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
);


--
-- Name: login_records_default; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.login_records_default (
    id bigint DEFAULT nextval('public.login_records_id_seq'::regclass) NOT NULL,
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
);


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
-- Name: messages_2026_01; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages_2026_01 (
    id bigint DEFAULT nextval('public.messages_id_seq'::regclass) NOT NULL,
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
);


--
-- Name: messages_2026_02; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages_2026_02 (
    id bigint DEFAULT nextval('public.messages_id_seq'::regclass) NOT NULL,
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
);


--
-- Name: messages_2026_03; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages_2026_03 (
    id bigint DEFAULT nextval('public.messages_id_seq'::regclass) NOT NULL,
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
);


--
-- Name: messages_default; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages_default (
    id bigint DEFAULT nextval('public.messages_id_seq'::regclass) NOT NULL,
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
);


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
-- Name: public_share_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.public_share_links (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    token character varying(10) NOT NULL,
    resource_type character varying(20) NOT NULL,
    resource_id character varying(500) NOT NULL,
    created_by character varying(100) NOT NULL,
    expires_at timestamp with time zone,
    access_count integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL,
    content text,
    content_type character varying(50),
    filename character varying(255),
    password_hash character varying(255),
    attempt_count integer DEFAULT 0 NOT NULL,
    locked_at timestamp with time zone
);


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
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(100) NOT NULL,
    display_name character varying(100),
    preferences jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    last_login_at timestamp with time zone,
    tenant_id uuid NOT NULL,
    role character varying(50) DEFAULT 'user'::character varying NOT NULL,
    password_hash character varying(255),
    email character varying(255),
    password_changed_at timestamp with time zone,
    must_change_password boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);


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
-- Name: ai_logs_2025_12; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_logs ATTACH PARTITION public.ai_logs_2025_12 FOR VALUES FROM ('2025-12-01 00:00:00+00') TO ('2026-01-01 00:00:00+00');


--
-- Name: ai_logs_2026_01; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_logs ATTACH PARTITION public.ai_logs_2026_01 FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-02-01 00:00:00+00');


--
-- Name: ai_logs_2026_02; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_logs ATTACH PARTITION public.ai_logs_2026_02 FOR VALUES FROM ('2026-02-01 00:00:00+00') TO ('2026-03-01 00:00:00+00');


--
-- Name: login_records_2026_01; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records ATTACH PARTITION public.login_records_2026_01 FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');


--
-- Name: login_records_2026_02; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records ATTACH PARTITION public.login_records_2026_02 FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');


--
-- Name: login_records_2026_03; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records ATTACH PARTITION public.login_records_2026_03 FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');


--
-- Name: login_records_default; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records ATTACH PARTITION public.login_records_default DEFAULT;


--
-- Name: messages_2026_01; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages ATTACH PARTITION public.messages_2026_01 FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');


--
-- Name: messages_2026_02; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages ATTACH PARTITION public.messages_2026_02 FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');


--
-- Name: messages_2026_03; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages ATTACH PARTITION public.messages_2026_03 FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');


--
-- Name: messages_default; Type: TABLE ATTACH; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages ATTACH PARTITION public.messages_default DEFAULT;


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
-- Name: ai_logs_2025_12 ai_logs_2025_12_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_logs_2025_12
    ADD CONSTRAINT ai_logs_2025_12_pkey PRIMARY KEY (id, created_at);


--
-- Name: ai_logs_2026_01 ai_logs_2026_01_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_logs_2026_01
    ADD CONSTRAINT ai_logs_2026_01_pkey PRIMARY KEY (id, created_at);


--
-- Name: ai_logs_2026_02 ai_logs_2026_02_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_logs_2026_02
    ADD CONSTRAINT ai_logs_2026_02_pkey PRIMARY KEY (id, created_at);


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
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: bot_binding_codes bot_binding_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_binding_codes
    ADD CONSTRAINT bot_binding_codes_pkey PRIMARY KEY (id);


--
-- Name: bot_files bot_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_files
    ADD CONSTRAINT bot_files_pkey PRIMARY KEY (id);


--
-- Name: bot_group_memories bot_group_memories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_group_memories
    ADD CONSTRAINT bot_group_memories_pkey PRIMARY KEY (id);


--
-- Name: bot_groups bot_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_groups
    ADD CONSTRAINT bot_groups_pkey PRIMARY KEY (id);


--
-- Name: bot_messages bot_messages_message_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_messages
    ADD CONSTRAINT bot_messages_message_id_key UNIQUE (message_id);


--
-- Name: bot_messages bot_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_messages
    ADD CONSTRAINT bot_messages_pkey PRIMARY KEY (id);


--
-- Name: bot_user_memories bot_user_memories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_user_memories
    ADD CONSTRAINT bot_user_memories_pkey PRIMARY KEY (id);


--
-- Name: bot_users bot_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_users
    ADD CONSTRAINT bot_users_pkey PRIMARY KEY (id);


--
-- Name: login_records login_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records
    ADD CONSTRAINT login_records_pkey PRIMARY KEY (id, partition_date);


--
-- Name: login_records_2026_01 login_records_2026_01_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records_2026_01
    ADD CONSTRAINT login_records_2026_01_pkey PRIMARY KEY (id, partition_date);


--
-- Name: login_records_2026_02 login_records_2026_02_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records_2026_02
    ADD CONSTRAINT login_records_2026_02_pkey PRIMARY KEY (id, partition_date);


--
-- Name: login_records_2026_03 login_records_2026_03_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records_2026_03
    ADD CONSTRAINT login_records_2026_03_pkey PRIMARY KEY (id, partition_date);


--
-- Name: login_records_default login_records_default_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records_default
    ADD CONSTRAINT login_records_default_pkey PRIMARY KEY (id, partition_date);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id, partition_date);


--
-- Name: messages_2026_01 messages_2026_01_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages_2026_01
    ADD CONSTRAINT messages_2026_01_pkey PRIMARY KEY (id, partition_date);


--
-- Name: messages_2026_02 messages_2026_02_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages_2026_02
    ADD CONSTRAINT messages_2026_02_pkey PRIMARY KEY (id, partition_date);


--
-- Name: messages_2026_03 messages_2026_03_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages_2026_03
    ADD CONSTRAINT messages_2026_03_pkey PRIMARY KEY (id, partition_date);


--
-- Name: messages_default messages_default_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages_default
    ADD CONSTRAINT messages_default_pkey PRIMARY KEY (id, partition_date);


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
-- Name: idx_ai_logs_agent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_agent_id ON ONLY public.ai_logs USING btree (agent_id);


--
-- Name: ai_logs_2025_12_agent_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2025_12_agent_id_idx ON public.ai_logs_2025_12 USING btree (agent_id);


--
-- Name: idx_ai_logs_context; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_context ON ONLY public.ai_logs USING btree (context_type, context_id);


--
-- Name: ai_logs_2025_12_context_type_context_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2025_12_context_type_context_id_idx ON public.ai_logs_2025_12 USING btree (context_type, context_id);


--
-- Name: idx_ai_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_created_at ON ONLY public.ai_logs USING btree (created_at DESC);


--
-- Name: ai_logs_2025_12_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2025_12_created_at_idx ON public.ai_logs_2025_12 USING btree (created_at DESC);


--
-- Name: idx_ai_logs_success; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_success ON ONLY public.ai_logs USING btree (success);


--
-- Name: ai_logs_2025_12_success_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2025_12_success_idx ON public.ai_logs_2025_12 USING btree (success);


--
-- Name: idx_ai_logs_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_tenant_created ON ONLY public.ai_logs USING btree (tenant_id, created_at);


--
-- Name: ai_logs_2025_12_tenant_id_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2025_12_tenant_id_created_at_idx ON public.ai_logs_2025_12 USING btree (tenant_id, created_at);


--
-- Name: idx_ai_logs_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_logs_tenant_id ON ONLY public.ai_logs USING btree (tenant_id);


--
-- Name: ai_logs_2025_12_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2025_12_tenant_id_idx ON public.ai_logs_2025_12 USING btree (tenant_id);


--
-- Name: ai_logs_2026_01_agent_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_01_agent_id_idx ON public.ai_logs_2026_01 USING btree (agent_id);


--
-- Name: ai_logs_2026_01_context_type_context_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_01_context_type_context_id_idx ON public.ai_logs_2026_01 USING btree (context_type, context_id);


--
-- Name: ai_logs_2026_01_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_01_created_at_idx ON public.ai_logs_2026_01 USING btree (created_at DESC);


--
-- Name: ai_logs_2026_01_success_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_01_success_idx ON public.ai_logs_2026_01 USING btree (success);


--
-- Name: ai_logs_2026_01_tenant_id_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_01_tenant_id_created_at_idx ON public.ai_logs_2026_01 USING btree (tenant_id, created_at);


--
-- Name: ai_logs_2026_01_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_01_tenant_id_idx ON public.ai_logs_2026_01 USING btree (tenant_id);


--
-- Name: ai_logs_2026_02_agent_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_02_agent_id_idx ON public.ai_logs_2026_02 USING btree (agent_id);


--
-- Name: ai_logs_2026_02_context_type_context_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_02_context_type_context_id_idx ON public.ai_logs_2026_02 USING btree (context_type, context_id);


--
-- Name: ai_logs_2026_02_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_02_created_at_idx ON public.ai_logs_2026_02 USING btree (created_at DESC);


--
-- Name: ai_logs_2026_02_success_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_02_success_idx ON public.ai_logs_2026_02 USING btree (success);


--
-- Name: ai_logs_2026_02_tenant_id_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_02_tenant_id_created_at_idx ON public.ai_logs_2026_02 USING btree (tenant_id, created_at);


--
-- Name: ai_logs_2026_02_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_logs_2026_02_tenant_id_idx ON public.ai_logs_2026_02 USING btree (tenant_id);


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

CREATE INDEX idx_binding_codes_code ON public.bot_binding_codes USING btree (code);


--
-- Name: idx_binding_codes_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_binding_codes_user_id ON public.bot_binding_codes USING btree (user_id);


--
-- Name: idx_bot_binding_codes_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_binding_codes_tenant_id ON public.bot_binding_codes USING btree (tenant_id);


--
-- Name: idx_bot_files_file_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_files_file_type ON public.bot_files USING btree (file_type);


--
-- Name: idx_bot_files_message_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_files_message_id ON public.bot_files USING btree (message_id);


--
-- Name: idx_bot_files_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_files_tenant_id ON public.bot_files USING btree (tenant_id);


--
-- Name: idx_bot_group_memories_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_group_memories_active ON public.bot_group_memories USING btree (bot_group_id, is_active);


--
-- Name: idx_bot_group_memories_bot_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_group_memories_bot_group_id ON public.bot_group_memories USING btree (bot_group_id);


--
-- Name: idx_bot_groups_platform_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_groups_platform_group_id ON public.bot_groups USING btree (platform_group_id);


--
-- Name: idx_bot_groups_platform_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_groups_platform_type ON public.bot_groups USING btree (platform_type);


--
-- Name: idx_bot_groups_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_groups_project_id ON public.bot_groups USING btree (project_id);


--
-- Name: idx_bot_groups_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_groups_tenant_id ON public.bot_groups USING btree (tenant_id);


--
-- Name: idx_bot_groups_tenant_platform_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_bot_groups_tenant_platform_unique ON public.bot_groups USING btree (tenant_id, platform_type, platform_group_id);


--
-- Name: idx_bot_messages_bot_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_messages_bot_group_id ON public.bot_messages USING btree (bot_group_id);


--
-- Name: idx_bot_messages_bot_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_messages_bot_user_id ON public.bot_messages USING btree (bot_user_id);


--
-- Name: idx_bot_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_messages_created_at ON public.bot_messages USING btree (created_at DESC);


--
-- Name: idx_bot_messages_message_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_messages_message_type ON public.bot_messages USING btree (message_type);


--
-- Name: idx_bot_messages_platform_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_messages_platform_type ON public.bot_messages USING btree (platform_type);


--
-- Name: idx_bot_messages_tenant_group; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_messages_tenant_group ON public.bot_messages USING btree (tenant_id, bot_group_id);


--
-- Name: idx_bot_messages_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_messages_tenant_id ON public.bot_messages USING btree (tenant_id);


--
-- Name: idx_bot_user_memories_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_user_memories_active ON public.bot_user_memories USING btree (bot_user_id, is_active);


--
-- Name: idx_bot_user_memories_bot_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_user_memories_bot_user_id ON public.bot_user_memories USING btree (bot_user_id);


--
-- Name: idx_bot_users_platform_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_users_platform_type ON public.bot_users USING btree (platform_type);


--
-- Name: idx_bot_users_platform_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_users_platform_user_id ON public.bot_users USING btree (platform_user_id);


--
-- Name: idx_bot_users_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_users_tenant_id ON public.bot_users USING btree (tenant_id);


--
-- Name: idx_bot_users_tenant_platform; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_users_tenant_platform ON public.bot_users USING btree (tenant_id, platform_user_id);


--
-- Name: idx_bot_users_tenant_platform_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_bot_users_tenant_platform_unique ON public.bot_users USING btree (tenant_id, platform_type, platform_user_id);


--
-- Name: idx_bot_users_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_users_user_id ON public.bot_users USING btree (user_id);


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
-- Name: login_records_2026_01_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_01_created_at_idx ON public.login_records_2026_01 USING btree (created_at DESC);


--
-- Name: login_records_2026_01_device_fingerprint_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_01_device_fingerprint_idx ON public.login_records_2026_01 USING btree (device_fingerprint);


--
-- Name: login_records_2026_01_ip_address_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_01_ip_address_idx ON public.login_records_2026_01 USING btree (ip_address);


--
-- Name: login_records_2026_01_success_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_01_success_idx ON public.login_records_2026_01 USING btree (success);


--
-- Name: login_records_2026_01_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_01_tenant_id_idx ON public.login_records_2026_01 USING btree (tenant_id);


--
-- Name: login_records_2026_01_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_01_user_id_idx ON public.login_records_2026_01 USING btree (user_id);


--
-- Name: login_records_2026_01_username_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_01_username_idx ON public.login_records_2026_01 USING btree (username);


--
-- Name: login_records_2026_02_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_02_created_at_idx ON public.login_records_2026_02 USING btree (created_at DESC);


--
-- Name: login_records_2026_02_device_fingerprint_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_02_device_fingerprint_idx ON public.login_records_2026_02 USING btree (device_fingerprint);


--
-- Name: login_records_2026_02_ip_address_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_02_ip_address_idx ON public.login_records_2026_02 USING btree (ip_address);


--
-- Name: login_records_2026_02_success_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_02_success_idx ON public.login_records_2026_02 USING btree (success);


--
-- Name: login_records_2026_02_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_02_tenant_id_idx ON public.login_records_2026_02 USING btree (tenant_id);


--
-- Name: login_records_2026_02_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_02_user_id_idx ON public.login_records_2026_02 USING btree (user_id);


--
-- Name: login_records_2026_02_username_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_02_username_idx ON public.login_records_2026_02 USING btree (username);


--
-- Name: login_records_2026_03_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_03_created_at_idx ON public.login_records_2026_03 USING btree (created_at DESC);


--
-- Name: login_records_2026_03_device_fingerprint_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_03_device_fingerprint_idx ON public.login_records_2026_03 USING btree (device_fingerprint);


--
-- Name: login_records_2026_03_ip_address_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_03_ip_address_idx ON public.login_records_2026_03 USING btree (ip_address);


--
-- Name: login_records_2026_03_success_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_03_success_idx ON public.login_records_2026_03 USING btree (success);


--
-- Name: login_records_2026_03_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_03_tenant_id_idx ON public.login_records_2026_03 USING btree (tenant_id);


--
-- Name: login_records_2026_03_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_03_user_id_idx ON public.login_records_2026_03 USING btree (user_id);


--
-- Name: login_records_2026_03_username_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_2026_03_username_idx ON public.login_records_2026_03 USING btree (username);


--
-- Name: login_records_default_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_default_created_at_idx ON public.login_records_default USING btree (created_at DESC);


--
-- Name: login_records_default_device_fingerprint_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_default_device_fingerprint_idx ON public.login_records_default USING btree (device_fingerprint);


--
-- Name: login_records_default_ip_address_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_default_ip_address_idx ON public.login_records_default USING btree (ip_address);


--
-- Name: login_records_default_success_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_default_success_idx ON public.login_records_default USING btree (success);


--
-- Name: login_records_default_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_default_tenant_id_idx ON public.login_records_default USING btree (tenant_id);


--
-- Name: login_records_default_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_default_user_id_idx ON public.login_records_default USING btree (user_id);


--
-- Name: login_records_default_username_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX login_records_default_username_idx ON public.login_records_default USING btree (username);


--
-- Name: messages_2026_01_category_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_01_category_idx ON public.messages_2026_01 USING btree (category);


--
-- Name: messages_2026_01_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_01_created_at_idx ON public.messages_2026_01 USING btree (created_at DESC);


--
-- Name: messages_2026_01_is_read_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_01_is_read_idx ON public.messages_2026_01 USING btree (is_read) WHERE (is_read = false);


--
-- Name: messages_2026_01_severity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_01_severity_idx ON public.messages_2026_01 USING btree (severity);


--
-- Name: messages_2026_01_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_01_source_idx ON public.messages_2026_01 USING btree (source);


--
-- Name: messages_2026_01_tenant_id_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_01_tenant_id_created_at_idx ON public.messages_2026_01 USING btree (tenant_id, created_at);


--
-- Name: messages_2026_01_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_01_tenant_id_idx ON public.messages_2026_01 USING btree (tenant_id);


--
-- Name: messages_2026_01_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_01_user_id_idx ON public.messages_2026_01 USING btree (user_id);


--
-- Name: messages_2026_02_category_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_02_category_idx ON public.messages_2026_02 USING btree (category);


--
-- Name: messages_2026_02_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_02_created_at_idx ON public.messages_2026_02 USING btree (created_at DESC);


--
-- Name: messages_2026_02_is_read_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_02_is_read_idx ON public.messages_2026_02 USING btree (is_read) WHERE (is_read = false);


--
-- Name: messages_2026_02_severity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_02_severity_idx ON public.messages_2026_02 USING btree (severity);


--
-- Name: messages_2026_02_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_02_source_idx ON public.messages_2026_02 USING btree (source);


--
-- Name: messages_2026_02_tenant_id_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_02_tenant_id_created_at_idx ON public.messages_2026_02 USING btree (tenant_id, created_at);


--
-- Name: messages_2026_02_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_02_tenant_id_idx ON public.messages_2026_02 USING btree (tenant_id);


--
-- Name: messages_2026_02_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_02_user_id_idx ON public.messages_2026_02 USING btree (user_id);


--
-- Name: messages_2026_03_category_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_03_category_idx ON public.messages_2026_03 USING btree (category);


--
-- Name: messages_2026_03_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_03_created_at_idx ON public.messages_2026_03 USING btree (created_at DESC);


--
-- Name: messages_2026_03_is_read_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_03_is_read_idx ON public.messages_2026_03 USING btree (is_read) WHERE (is_read = false);


--
-- Name: messages_2026_03_severity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_03_severity_idx ON public.messages_2026_03 USING btree (severity);


--
-- Name: messages_2026_03_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_03_source_idx ON public.messages_2026_03 USING btree (source);


--
-- Name: messages_2026_03_tenant_id_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_03_tenant_id_created_at_idx ON public.messages_2026_03 USING btree (tenant_id, created_at);


--
-- Name: messages_2026_03_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_03_tenant_id_idx ON public.messages_2026_03 USING btree (tenant_id);


--
-- Name: messages_2026_03_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_2026_03_user_id_idx ON public.messages_2026_03 USING btree (user_id);


--
-- Name: messages_default_category_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_default_category_idx ON public.messages_default USING btree (category);


--
-- Name: messages_default_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_default_created_at_idx ON public.messages_default USING btree (created_at DESC);


--
-- Name: messages_default_is_read_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_default_is_read_idx ON public.messages_default USING btree (is_read) WHERE (is_read = false);


--
-- Name: messages_default_severity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_default_severity_idx ON public.messages_default USING btree (severity);


--
-- Name: messages_default_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_default_source_idx ON public.messages_default USING btree (source);


--
-- Name: messages_default_tenant_id_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_default_tenant_id_created_at_idx ON public.messages_default USING btree (tenant_id, created_at);


--
-- Name: messages_default_tenant_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_default_tenant_id_idx ON public.messages_default USING btree (tenant_id);


--
-- Name: messages_default_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_default_user_id_idx ON public.messages_default USING btree (user_id);


--
-- Name: ai_logs_2025_12_agent_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_agent_id ATTACH PARTITION public.ai_logs_2025_12_agent_id_idx;


--
-- Name: ai_logs_2025_12_context_type_context_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_context ATTACH PARTITION public.ai_logs_2025_12_context_type_context_id_idx;


--
-- Name: ai_logs_2025_12_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_created_at ATTACH PARTITION public.ai_logs_2025_12_created_at_idx;


--
-- Name: ai_logs_2025_12_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.ai_logs_pkey ATTACH PARTITION public.ai_logs_2025_12_pkey;


--
-- Name: ai_logs_2025_12_success_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_success ATTACH PARTITION public.ai_logs_2025_12_success_idx;


--
-- Name: ai_logs_2025_12_tenant_id_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_tenant_created ATTACH PARTITION public.ai_logs_2025_12_tenant_id_created_at_idx;


--
-- Name: ai_logs_2025_12_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_tenant_id ATTACH PARTITION public.ai_logs_2025_12_tenant_id_idx;


--
-- Name: ai_logs_2026_01_agent_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_agent_id ATTACH PARTITION public.ai_logs_2026_01_agent_id_idx;


--
-- Name: ai_logs_2026_01_context_type_context_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_context ATTACH PARTITION public.ai_logs_2026_01_context_type_context_id_idx;


--
-- Name: ai_logs_2026_01_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_created_at ATTACH PARTITION public.ai_logs_2026_01_created_at_idx;


--
-- Name: ai_logs_2026_01_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.ai_logs_pkey ATTACH PARTITION public.ai_logs_2026_01_pkey;


--
-- Name: ai_logs_2026_01_success_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_success ATTACH PARTITION public.ai_logs_2026_01_success_idx;


--
-- Name: ai_logs_2026_01_tenant_id_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_tenant_created ATTACH PARTITION public.ai_logs_2026_01_tenant_id_created_at_idx;


--
-- Name: ai_logs_2026_01_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_tenant_id ATTACH PARTITION public.ai_logs_2026_01_tenant_id_idx;


--
-- Name: ai_logs_2026_02_agent_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_agent_id ATTACH PARTITION public.ai_logs_2026_02_agent_id_idx;


--
-- Name: ai_logs_2026_02_context_type_context_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_context ATTACH PARTITION public.ai_logs_2026_02_context_type_context_id_idx;


--
-- Name: ai_logs_2026_02_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_created_at ATTACH PARTITION public.ai_logs_2026_02_created_at_idx;


--
-- Name: ai_logs_2026_02_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.ai_logs_pkey ATTACH PARTITION public.ai_logs_2026_02_pkey;


--
-- Name: ai_logs_2026_02_success_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_success ATTACH PARTITION public.ai_logs_2026_02_success_idx;


--
-- Name: ai_logs_2026_02_tenant_id_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_tenant_created ATTACH PARTITION public.ai_logs_2026_02_tenant_id_created_at_idx;


--
-- Name: ai_logs_2026_02_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_ai_logs_tenant_id ATTACH PARTITION public.ai_logs_2026_02_tenant_id_idx;


--
-- Name: login_records_2026_01_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_created_at ATTACH PARTITION public.login_records_2026_01_created_at_idx;


--
-- Name: login_records_2026_01_device_fingerprint_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_device_fingerprint ATTACH PARTITION public.login_records_2026_01_device_fingerprint_idx;


--
-- Name: login_records_2026_01_ip_address_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_ip_address ATTACH PARTITION public.login_records_2026_01_ip_address_idx;


--
-- Name: login_records_2026_01_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.login_records_pkey ATTACH PARTITION public.login_records_2026_01_pkey;


--
-- Name: login_records_2026_01_success_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_success ATTACH PARTITION public.login_records_2026_01_success_idx;


--
-- Name: login_records_2026_01_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_tenant_id ATTACH PARTITION public.login_records_2026_01_tenant_id_idx;


--
-- Name: login_records_2026_01_user_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_user_id ATTACH PARTITION public.login_records_2026_01_user_id_idx;


--
-- Name: login_records_2026_01_username_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_username ATTACH PARTITION public.login_records_2026_01_username_idx;


--
-- Name: login_records_2026_02_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_created_at ATTACH PARTITION public.login_records_2026_02_created_at_idx;


--
-- Name: login_records_2026_02_device_fingerprint_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_device_fingerprint ATTACH PARTITION public.login_records_2026_02_device_fingerprint_idx;


--
-- Name: login_records_2026_02_ip_address_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_ip_address ATTACH PARTITION public.login_records_2026_02_ip_address_idx;


--
-- Name: login_records_2026_02_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.login_records_pkey ATTACH PARTITION public.login_records_2026_02_pkey;


--
-- Name: login_records_2026_02_success_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_success ATTACH PARTITION public.login_records_2026_02_success_idx;


--
-- Name: login_records_2026_02_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_tenant_id ATTACH PARTITION public.login_records_2026_02_tenant_id_idx;


--
-- Name: login_records_2026_02_user_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_user_id ATTACH PARTITION public.login_records_2026_02_user_id_idx;


--
-- Name: login_records_2026_02_username_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_username ATTACH PARTITION public.login_records_2026_02_username_idx;


--
-- Name: login_records_2026_03_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_created_at ATTACH PARTITION public.login_records_2026_03_created_at_idx;


--
-- Name: login_records_2026_03_device_fingerprint_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_device_fingerprint ATTACH PARTITION public.login_records_2026_03_device_fingerprint_idx;


--
-- Name: login_records_2026_03_ip_address_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_ip_address ATTACH PARTITION public.login_records_2026_03_ip_address_idx;


--
-- Name: login_records_2026_03_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.login_records_pkey ATTACH PARTITION public.login_records_2026_03_pkey;


--
-- Name: login_records_2026_03_success_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_success ATTACH PARTITION public.login_records_2026_03_success_idx;


--
-- Name: login_records_2026_03_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_tenant_id ATTACH PARTITION public.login_records_2026_03_tenant_id_idx;


--
-- Name: login_records_2026_03_user_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_user_id ATTACH PARTITION public.login_records_2026_03_user_id_idx;


--
-- Name: login_records_2026_03_username_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_username ATTACH PARTITION public.login_records_2026_03_username_idx;


--
-- Name: login_records_default_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_created_at ATTACH PARTITION public.login_records_default_created_at_idx;


--
-- Name: login_records_default_device_fingerprint_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_device_fingerprint ATTACH PARTITION public.login_records_default_device_fingerprint_idx;


--
-- Name: login_records_default_ip_address_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_ip_address ATTACH PARTITION public.login_records_default_ip_address_idx;


--
-- Name: login_records_default_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.login_records_pkey ATTACH PARTITION public.login_records_default_pkey;


--
-- Name: login_records_default_success_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_success ATTACH PARTITION public.login_records_default_success_idx;


--
-- Name: login_records_default_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_tenant_id ATTACH PARTITION public.login_records_default_tenant_id_idx;


--
-- Name: login_records_default_user_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_user_id ATTACH PARTITION public.login_records_default_user_id_idx;


--
-- Name: login_records_default_username_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_login_records_username ATTACH PARTITION public.login_records_default_username_idx;


--
-- Name: messages_2026_01_category_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_category ATTACH PARTITION public.messages_2026_01_category_idx;


--
-- Name: messages_2026_01_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_created_at ATTACH PARTITION public.messages_2026_01_created_at_idx;


--
-- Name: messages_2026_01_is_read_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_is_read ATTACH PARTITION public.messages_2026_01_is_read_idx;


--
-- Name: messages_2026_01_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.messages_pkey ATTACH PARTITION public.messages_2026_01_pkey;


--
-- Name: messages_2026_01_severity_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_severity ATTACH PARTITION public.messages_2026_01_severity_idx;


--
-- Name: messages_2026_01_source_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_source ATTACH PARTITION public.messages_2026_01_source_idx;


--
-- Name: messages_2026_01_tenant_id_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_tenant_created ATTACH PARTITION public.messages_2026_01_tenant_id_created_at_idx;


--
-- Name: messages_2026_01_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_tenant_id ATTACH PARTITION public.messages_2026_01_tenant_id_idx;


--
-- Name: messages_2026_01_user_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_user_id ATTACH PARTITION public.messages_2026_01_user_id_idx;


--
-- Name: messages_2026_02_category_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_category ATTACH PARTITION public.messages_2026_02_category_idx;


--
-- Name: messages_2026_02_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_created_at ATTACH PARTITION public.messages_2026_02_created_at_idx;


--
-- Name: messages_2026_02_is_read_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_is_read ATTACH PARTITION public.messages_2026_02_is_read_idx;


--
-- Name: messages_2026_02_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.messages_pkey ATTACH PARTITION public.messages_2026_02_pkey;


--
-- Name: messages_2026_02_severity_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_severity ATTACH PARTITION public.messages_2026_02_severity_idx;


--
-- Name: messages_2026_02_source_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_source ATTACH PARTITION public.messages_2026_02_source_idx;


--
-- Name: messages_2026_02_tenant_id_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_tenant_created ATTACH PARTITION public.messages_2026_02_tenant_id_created_at_idx;


--
-- Name: messages_2026_02_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_tenant_id ATTACH PARTITION public.messages_2026_02_tenant_id_idx;


--
-- Name: messages_2026_02_user_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_user_id ATTACH PARTITION public.messages_2026_02_user_id_idx;


--
-- Name: messages_2026_03_category_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_category ATTACH PARTITION public.messages_2026_03_category_idx;


--
-- Name: messages_2026_03_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_created_at ATTACH PARTITION public.messages_2026_03_created_at_idx;


--
-- Name: messages_2026_03_is_read_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_is_read ATTACH PARTITION public.messages_2026_03_is_read_idx;


--
-- Name: messages_2026_03_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.messages_pkey ATTACH PARTITION public.messages_2026_03_pkey;


--
-- Name: messages_2026_03_severity_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_severity ATTACH PARTITION public.messages_2026_03_severity_idx;


--
-- Name: messages_2026_03_source_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_source ATTACH PARTITION public.messages_2026_03_source_idx;


--
-- Name: messages_2026_03_tenant_id_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_tenant_created ATTACH PARTITION public.messages_2026_03_tenant_id_created_at_idx;


--
-- Name: messages_2026_03_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_tenant_id ATTACH PARTITION public.messages_2026_03_tenant_id_idx;


--
-- Name: messages_2026_03_user_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_user_id ATTACH PARTITION public.messages_2026_03_user_id_idx;


--
-- Name: messages_default_category_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_category ATTACH PARTITION public.messages_default_category_idx;


--
-- Name: messages_default_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_created_at ATTACH PARTITION public.messages_default_created_at_idx;


--
-- Name: messages_default_is_read_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_is_read ATTACH PARTITION public.messages_default_is_read_idx;


--
-- Name: messages_default_pkey; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.messages_pkey ATTACH PARTITION public.messages_default_pkey;


--
-- Name: messages_default_severity_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_severity ATTACH PARTITION public.messages_default_severity_idx;


--
-- Name: messages_default_source_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_source ATTACH PARTITION public.messages_default_source_idx;


--
-- Name: messages_default_tenant_id_created_at_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_tenant_created ATTACH PARTITION public.messages_default_tenant_id_created_at_idx;


--
-- Name: messages_default_tenant_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_tenant_id ATTACH PARTITION public.messages_default_tenant_id_idx;


--
-- Name: messages_default_user_id_idx; Type: INDEX ATTACH; Schema: public; Owner: -
--

ALTER INDEX public.idx_messages_user_id ATTACH PARTITION public.messages_default_user_id_idx;


--
-- Name: tenants trigger_tenants_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_tenants_updated_at BEFORE UPDATE ON public.tenants FOR EACH ROW EXECUTE FUNCTION public.update_tenants_updated_at();


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
-- Name: bot_binding_codes bot_binding_codes_used_by_bot_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_binding_codes
    ADD CONSTRAINT bot_binding_codes_used_by_bot_user_id_fkey FOREIGN KEY (used_by_bot_user_id) REFERENCES public.bot_users(id) ON DELETE SET NULL;


--
-- Name: bot_binding_codes bot_binding_codes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_binding_codes
    ADD CONSTRAINT bot_binding_codes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: bot_files bot_files_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_files
    ADD CONSTRAINT bot_files_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.bot_messages(id) ON DELETE CASCADE;


--
-- Name: bot_group_memories bot_group_memories_bot_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_group_memories
    ADD CONSTRAINT bot_group_memories_bot_group_id_fkey FOREIGN KEY (bot_group_id) REFERENCES public.bot_groups(id) ON DELETE CASCADE;


--
-- Name: bot_group_memories bot_group_memories_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_group_memories
    ADD CONSTRAINT bot_group_memories_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.bot_users(id) ON DELETE SET NULL;


--
-- Name: bot_messages bot_messages_bot_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_messages
    ADD CONSTRAINT bot_messages_bot_group_id_fkey FOREIGN KEY (bot_group_id) REFERENCES public.bot_groups(id) ON DELETE CASCADE;


--
-- Name: bot_messages bot_messages_bot_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_messages
    ADD CONSTRAINT bot_messages_bot_user_id_fkey FOREIGN KEY (bot_user_id) REFERENCES public.bot_users(id) ON DELETE CASCADE;


--
-- Name: bot_user_memories bot_user_memories_bot_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_user_memories
    ADD CONSTRAINT bot_user_memories_bot_user_id_fkey FOREIGN KEY (bot_user_id) REFERENCES public.bot_users(id) ON DELETE CASCADE;


--
-- Name: bot_users bot_users_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_users
    ADD CONSTRAINT bot_users_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


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
-- Name: bot_binding_codes fk_bot_binding_codes_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_binding_codes
    ADD CONSTRAINT fk_bot_binding_codes_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: bot_files fk_bot_files_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_files
    ADD CONSTRAINT fk_bot_files_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: bot_groups fk_bot_groups_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_groups
    ADD CONSTRAINT fk_bot_groups_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: bot_messages fk_bot_messages_file_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_messages
    ADD CONSTRAINT fk_bot_messages_file_id FOREIGN KEY (file_id) REFERENCES public.bot_files(id) ON DELETE SET NULL;


--
-- Name: bot_messages fk_bot_messages_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_messages
    ADD CONSTRAINT fk_bot_messages_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: bot_users fk_bot_users_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_users
    ADD CONSTRAINT fk_bot_users_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


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

\unrestrict B3zAt31VAvJjuvFyyx5hiB89dSnTRde1vhoLIujIBB41QJw9GGoHdACrXbvMykE

