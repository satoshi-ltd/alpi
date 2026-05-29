---
name: sql-query
description: Write a SQL query for a business question — with the question translated, the query explained, and caveats on what it does not answer
category: data
version: 0.1.0
origin: user
requires_env: []
tools: [db, terminal]
keywords: [sql, query, analytics, database, data]
created_at: 2026-05-05
---

## When to use
When a business question needs to be answered from a database and the requester either doesn't know SQL or needs a reviewed, production-safe query. Also use to audit an existing query for correctness, performance risk, or missing edge case handling.

## Output format

**Business question** — what decision does this query support? Restate it in plain language before translating to SQL. If the question is ambiguous, resolve the ambiguity before writing code.

**Assumptions**
- Which table(s) contain the relevant data
- Date range and any filters applied
- How nulls are handled (exclude / count as zero / flag)
- Deduplication logic if records can appear multiple times

**Query**

```sql
-- [one-line comment explaining the intent]
SELECT
  ...
FROM ...
WHERE ...
GROUP BY ...
ORDER BY ...
```

**What this query answers** — the exact interpretation of the result.

**What this query does not answer** — limitations, blind spots, or conditions under which the result would be misleading.

**Performance notes** — for large tables: does this query scan the full table? Are the filter columns indexed? For queries that touch > 10M rows, flag the risk.

**Validation check** — one simple query to sanity-check the result before trusting it (e.g., count of raw rows vs. aggregated total).

## Approach
- Restate the business question before writing the query. Translating ambiguous questions into precise SQL produces precise wrong answers.
- Null handling is not optional. A SUM that ignores nulls and a SUM that treats them as zero produce different results. State which you're using and why.
- CTEs are preferable to nested subqueries for readability. A query a colleague can't read in 5 minutes is a liability.
- "What this query does not answer" is the most honest section. Every aggregation loses information. State what was lost.

## Data
Use `db` to query data loaded into the skill's SQLite state, or `terminal` to run `sqlite3` against any local data file the user provides. Before querying, inspect the schema: `PRAGMA table_info(<table>)` or `SELECT name FROM sqlite_master WHERE type='table'`. Never assume column names.
