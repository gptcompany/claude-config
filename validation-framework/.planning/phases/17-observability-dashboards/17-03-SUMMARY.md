# Plan 17-03 Summary: Grafana Dashboard Pack

**Phase:** 17-observability-dashboards
**Plan:** 03
**Status:** COMPLETE
**Completed:** 2026-01-26

## Objective

Create Grafana dashboard pack for validation metrics visualization with file provisioning.

## Tasks Completed

### Task 1: Dashboard Provisioning Config
- Created `/etc/grafana/provisioning/dashboards/validation.yaml`
- Points to `/var/lib/grafana/dashboards/validation` (system location)
- Uses "Validation" folder with folderUid `validation`
- Auto-refresh: 30 seconds

### Task 2: validation-overview.json Dashboard
- **8 panels** covering key validation metrics
- **Top row (stat panels):** Total runs, Overall pass rate, Tier 1 failures, Avg duration
- **Middle row (time series):** Pass rate by tier, Run volume
- **Bottom row (tables):** Failing validators, Recent failures
- Variables: `DS_QUESTDB` (datasource), `timeRange` (1/7/14/30 days)

### Task 3: validator-drilldown.json Dashboard
- **8 panels** for per-validator deep dive
- **Variables:** `dimension` dropdown (14 validators: syntax, tests, imports, lint, types, style, security, complexity, docs, coverage, performance, architecture, accessibility, i18n)
- **Panels:** Pass rate stat, Total runs, Failures, Avg duration, Pass rate trend, Duration trend, Failures by hour of day, Recent failures table
- Link back to validation-overview

### Task 4: project-comparison.json Dashboard
- **9 panels** for cross-project comparison
- **Top row:** Active projects count, Avg/Best/Lowest quality scores
- **Middle:** Quality score bar chart, Project statistics table
- **Bottom:** Quality score trend (top 5 projects), Assessment distribution pie chart, Recent assessments table
- Uses `claude_quality_scores` table

### Task 5: Grafana Restart & Verification
- Grafana restarted and healthy
- All 3 dashboards visible in "Validation" folder
- No provisioning errors for validation dashboards

## Files Created

| File | Location | Size |
|------|----------|------|
| validation-overview.json | /var/lib/grafana/dashboards/validation/ | 19.7 KB |
| validator-drilldown.json | /var/lib/grafana/dashboards/validation/ | 21.2 KB |
| project-comparison.json | /var/lib/grafana/dashboards/validation/ | 23.6 KB |
| validation.yaml | /etc/grafana/provisioning/dashboards/ | ~250 B |

## Technical Details

### Datasource Configuration
```json
"datasource": {
  "type": "questdb-questdb-datasource",
  "uid": "${DS_QUESTDB}"
}
```

### QuestDB Tables Used
- `validation` - raw validation results
- `claude_quality_scores` - project quality scores

### Key Queries
- Pass rate: `sum(passed) * 100.0 / count()`
- Tier classification: `CASE WHEN dimension IN ('syntax', 'tests', 'imports') THEN 'Tier 1' ...`
- Time bucketing: `timestamp_floor('h', timestamp)` with `SAMPLE BY 1h ALIGN TO CALENDAR`

## Verification Results

```bash
# Dashboard count in Validation folder
$ curl -s http://localhost:3000/api/search | jq '[.[] | select(.folderTitle=="Validation")] | length'
3

# Dashboard UIDs
- validation-overview
- validator-drilldown
- project-comparison

# Grafana health
$ curl -s http://localhost:3000/api/health
{"commit":"...","database":"ok","version":"11.4.0"}
```

## Access

- **URL:** http://localhost:3000/dashboards/f/validation/validation
- **Direct links:**
  - http://localhost:3000/d/validation-overview/validation-overview
  - http://localhost:3000/d/validator-drilldown/validator-drilldown
  - http://localhost:3000/d/project-comparison/project-comparison

## Notes

1. **Location change:** Dashboards stored in `/var/lib/grafana/dashboards/validation/` instead of `~/.claude/grafana/dashboards/` due to Grafana user permissions on home directory

2. **Helper scripts created:**
   - `~/.claude/grafana/setup-dashboards.sh` - installs dashboards to system location
   - `~/.claude/grafana/install-provisioning.sh` - installs provisioning config

3. **Source copies preserved:** Original dashboard JSON files remain in `~/.claude/grafana/dashboards/` for version control

## Next Steps (Plan 17-04)

- Configure Discord alert contact points
- Create validation alert rules
- Set up notification policies

---

*Generated: 2026-01-26*
*Plan: 17-03*
*Phase: 17-observability-dashboards*
