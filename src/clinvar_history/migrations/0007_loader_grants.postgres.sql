-- PostgreSQL only. 0005 gave the loader write access to the tables that
-- existed when it ran, and clinvar_variation_history arrived later in 0006, so
-- a load run as clinvar_history_loader failed on that table. 0005 is applied
-- and must not change; this grants the missing rights, and the default
-- privileges cover tables and sequences that later migrations create.
DO $$
BEGIN
    EXECUTE format(
        'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO clinvar_history_loader',
        current_schema()
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO clinvar_history_loader',
        current_schema()
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO clinvar_history_loader',
        current_schema()
    );
END
$$;
