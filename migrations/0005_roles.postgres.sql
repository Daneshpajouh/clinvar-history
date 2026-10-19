-- PostgreSQL only. Analysts get a read-only role so a mistyped UPDATE in an
-- ad hoc session cannot change a loaded release; the loader role writes.
-- Roles are cluster-wide, so creation is guarded for re-runs.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vwh_analyst') THEN
        CREATE ROLE vwh_analyst NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vwh_loader') THEN
        CREATE ROLE vwh_loader NOLOGIN;
    END IF;
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO vwh_analyst, vwh_loader', current_schema());
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO vwh_analyst', current_schema());
    EXECUTE format(
        'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO vwh_loader',
        current_schema()
    );
    EXECUTE format(
        'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO vwh_loader', current_schema()
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT ON TABLES TO vwh_analyst',
        current_schema()
    );
    REVOKE ALL ON schema_migrations FROM vwh_analyst;
END
$$;
