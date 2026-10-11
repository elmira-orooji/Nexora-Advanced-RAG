# Connector recovery

Scheduled and manual syncs acquire a lease row in the `sync_leases` table before
starting work. The lease includes an expiration timestamp and a unique owner ID.
A background heartbeat thread renews the lease every 30 seconds while the sync
is running. The scheduler revisits `syncing` rows, including interrupted manual
syncs with scheduling disabled. It resumes a row only if no valid (non-expired)
lease exists for it. Disabled schedules remain disabled after recovery.

If a worker crashes without releasing its lease, the lease expires after 5 minutes
and another worker can take over on the next scheduler tick (normally every 60
seconds). A hung process with a working heartbeat will retain ownership
indefinitely.

This implementation is compatible with PgBouncer in transaction pooling mode
because it does not rely on PostgreSQL session state or advisory locks. No
dedicated database connection is held for the duration of a sync.

Deployment requirements:

- Run `alembic upgrade head` to create the `sync_leases` table.
- Stop all old workers before starting this version: old workers do not use
  leases and must not overlap with the new scheduler.
- Works with direct PostgreSQL connections, session pooling, and transaction
  pooling (PgBouncer).

The regression tests simulate worker interleaving and lease ownership using
SQLite; they do not exercise process termination against a live PostgreSQL server.
