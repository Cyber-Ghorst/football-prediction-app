# Free fixture observation archive

## Purpose

The provider adapter milestone supplies normalized source observations. This
archive stores those observations immutably in the existing provider snapshot
store so they can be reviewed, crosswalked and reconciled later.

## Storage contract

- Provider namespace: one of OpenLigaDB, OpenFootball, Open Matchday,
  LiveScoreFootball or Bzzoiro.
- Resource type: future_fixture_observations.
- Each batch retains provider-scoped fixture IDs, source URLs, raw payloads,
  kickoff/status validation, licence notes and retrieval time.
- Credentials are forbidden in request metadata and are never stored.
- Snapshot IDs and provider collection-run IDs are returned for audit.
- Snapshots are append-only; TTL zero means the archive record is not expired.

## Safety boundary

This archive is not the canonical fixture repository. It writes zero canonical
fixtures and zero prediction-ledger rows. It does not change provider routing,
generate predictions or make a source prediction-ready. The canonical
competition/season/team crosswalk and per-competition quality review must be
completed before any staged observation can be promoted.

The archive uses the existing CockroachDB provider snapshot store and requires
PROVIDER_DATABASE_URL. It does not modify the Neon prediction ledger.
