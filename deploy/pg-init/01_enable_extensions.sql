-- ═══════════════════════════════════════════════════════════════
-- PostgreSQL Init: 01_enable_extensions.sql
-- 启用 Apache AGE 图引擎 + pgvector (预留)
-- 在 postgres 容器首次启动时自动执行
-- ═══════════════════════════════════════════════════════════════

-- 必须加载 AGE 库
LOAD 'age';

-- 在 pathfinder 数据库创建 AGE 扩展
\c pathfinder

CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector (预留)

-- 验证 AGE 安装
DO $$
BEGIN
    RAISE NOTICE 'Apache AGE version: %', (SELECT ag_catalog.ag_version());
END $$;
