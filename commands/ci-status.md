# /ci-status - View All CI Status

View CI status across all repositories from PostgreSQL.

## Usage

```
/ci-status              # Show all pending CI statuses
/ci-status --all        # Show all (including injected)
/ci-status --repo X     # Filter by repo name
```

## Execution

Query PostgreSQL for CI statuses:

```bash
PGPASSWORD=n8n psql -h localhost -p 5433 -U n8n -d n8n -c "
SELECT
    CASE conclusion
        WHEN 'success' THEN '✅'
        WHEN 'failure' THEN '❌'
        ELSE '⚠️'
    END as status,
    repo_name,
    branch,
    COALESCE('#' || pr_number::text, '-') as pr,
    conclusion,
    pending_action,
    CASE WHEN injected THEN 'yes' ELSE 'no' END as injected,
    to_char(created_at, 'MM-DD HH24:MI') as time
FROM ci_status
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 20;
"
```

## Output Format

Format as table:

```markdown
## CI Status (Last 24h)

| Status | Repo | Branch | PR | Conclusion | Action | Injected | Time |
|--------|------|--------|----|-----------:|--------|----------|------|
| ✅ | my-repo | main | #42 | success | merge | no | 01-12 14:30 |
| ❌ | other-repo | feature/x | #15 | failure | fix | yes | 01-12 13:15 |

**Legend:**
- ✅ success (ready to merge)
- ❌ failure (needs fix)
- ⚠️ cancelled/skipped
- Injected: "yes" = already shown in Claude session
```

## Filters

### --all flag
If user passes `--all`, include injected statuses:
```sql
-- Remove: AND injected = FALSE
```

### --repo flag
If user passes `--repo <name>`:
```sql
WHERE repo_name ILIKE '%<name>%'
```

## No Results

If no CI statuses found:

```
No CI statuses in the last 24 hours.

This means either:
- No CI workflows completed recently
- All statuses were already injected and cleared
- N8N workflow not yet configured to write to PostgreSQL
```

## Actions

After showing the table, offer actions:

```markdown
### Quick Actions

- **Merge ready PRs**: `gh pr merge <PR#> --squash`
- **View failed run**: Click run URL or `gh run view <run_id>`
- **Clear all injected**: Mark all as injected to reset
```

## Database Info

```
Host: localhost
Port: 5433
Database: n8n
Table: ci_status
```
