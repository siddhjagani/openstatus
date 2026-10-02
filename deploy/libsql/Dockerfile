# libsql-server pinned by digest (sqld 0.24.33, built 2026-08-23) so a moved
# :latest can never change the database underneath us, plus a query-based
# health check (healthcheck.pl).
FROM ghcr.io/tursodatabase/libsql-server@sha256:6dd3eb276d9d3604e4a48ac4a999a2e267814732d57d7e94c04ba71482333a67
COPY healthcheck.pl /usr/local/bin/libsql-healthcheck.pl
