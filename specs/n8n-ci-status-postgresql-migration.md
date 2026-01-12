# N8N Workflow Migration: File → PostgreSQL

**Version**: 2.0
**Date**: 2026-01-12
**Status**: Ready for Implementation
**Workflow ID**: LWTYUUKYE8FlOxsd

---

## Overview

Modificare il workflow "GitHub CI Status Notifier" per scrivere su PostgreSQL invece che su file.

## Motivazione

| File-Based | PostgreSQL |
|------------|------------|
| ❌ Race conditions | ✅ ACID transactions |
| ❌ No query | ✅ SQL queries |
| ❌ Manual cleanup | ✅ Auto-retention |
| ❌ Single machine | ✅ Multi-machine |

---

## Modifica Richiesta

### RIMUOVERE

```
Nodo: "Write Status File" (Execute Command o Write Binary File)
```

### AGGIUNGERE

```
Nodo: PostgreSQL
Tipo: Execute Query
```

---

## Configurazione Nodo PostgreSQL

### Credenziali

```yaml
Host: localhost (o postgres container name se in Docker network)
Port: 5432 (interno) / 5433 (esterno)
Database: n8n
User: n8n
Password: n8n
SSL: false (internal network)
```

**Nota**: Se N8N è nello stesso Docker network di PostgreSQL, usare il container name come host (es: `n8n-postgres-1`).

### Query INSERT

```sql
INSERT INTO ci_status (
    repo,
    repo_name,
    branch,
    pr_number,
    commit_sha,
    conclusion,
    run_url,
    message,
    pending_action
) VALUES (
    '{{ $json.repo }}',
    '{{ $json.repo_name }}',
    '{{ $json.branch }}',
    {{ $json.pr_number || 'NULL' }},
    '{{ $json.commit_sha }}',
    '{{ $json.conclusion }}',
    '{{ $json.run_url }}',
    '{{ $json.message }}',
    {{ $json.pending_action ? "'" + $json.pending_action + "'" : 'NULL' }}
)
RETURNING id;
```

### Alternativa: Query con Expressions

Se preferite usare le expressions N8N:

```sql
INSERT INTO ci_status (
    repo, repo_name, branch, pr_number, commit_sha,
    conclusion, run_url, message, pending_action
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9
)
RETURNING id;
```

Con parametri:
- $1: `{{ $json.repo }}`
- $2: `{{ $json.repo_name }}`
- $3: `{{ $json.branch }}`
- $4: `{{ $json.pr_number || null }}`
- $5: `{{ $json.commit_sha }}`
- $6: `{{ $json.conclusion }}`
- $7: `{{ $json.run_url }}`
- $8: `{{ $json.message }}`
- $9: `{{ $json.pending_action || null }}`

---

## Dati di Input (dal nodo Transform)

Il nodo "Transform Data" già produce questi campi:

```json
{
  "repo": "gptcompany/repo-name",
  "repo_name": "repo-name",
  "branch": "feature/my-feature",
  "pr_number": 42,
  "commit_sha": "abc123de",
  "conclusion": "success",
  "run_url": "https://github.com/...",
  "message": "CI passed on PR #42, ready to merge",
  "pending_action": "merge"
}
```

**Nessuna modifica al nodo Transform necessaria** - i dati sono già nel formato corretto.

---

## Schema Tabella (già creato)

```sql
CREATE TABLE ci_status (
    id SERIAL PRIMARY KEY,
    repo VARCHAR(255) NOT NULL,
    repo_name VARCHAR(100) NOT NULL,
    branch VARCHAR(255),
    pr_number INT,
    commit_sha VARCHAR(40),
    conclusion VARCHAR(50) NOT NULL,  -- success, failure, cancelled, skipped
    run_url TEXT,
    message TEXT,
    pending_action VARCHAR(50),        -- merge, fix, null
    injected BOOLEAN DEFAULT FALSE,    -- Claude Code sets this to true
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Flusso Aggiornato

```
┌─────────────────────┐
│  Webhook Node       │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  IF - Filter        │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Transform Data     │  (invariato)
└─────────┬───────────┘
          │
     ┌────┴────┐
     │         │
     ▼         ▼
┌─────────┐ ┌─────────────────┐
│Discord  │ │  PostgreSQL     │  ← NUOVO (sostituisce Write File)
│Router   │ │  INSERT INTO    │
└─────────┘ └─────────────────┘
```

---

## Test

### Verifica INSERT

Dopo il test curl, verificare:

```sql
SELECT * FROM ci_status ORDER BY created_at DESC LIMIT 5;
```

### Test Payload

```bash
curl -X POST "https://n8nubuntu.princyx.xyz/webhook/github-ci-status-notifier" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=<signature>" \
  -d '{
    "action": "completed",
    "workflow_run": {
      "id": 999999999,
      "name": "CI",
      "head_branch": "test-branch",
      "head_sha": "abc123def456789",
      "status": "completed",
      "conclusion": "success",
      "html_url": "https://github.com/test/repo/actions/runs/999",
      "created_at": "2026-01-12T10:00:00Z",
      "updated_at": "2026-01-12T10:02:00Z",
      "run_started_at": "2026-01-12T10:00:00Z",
      "pull_requests": [{"number": 123}]
    },
    "repository": {
      "name": "test-repo",
      "full_name": "gptcompany/test-repo",
      "html_url": "https://github.com/gptcompany/test-repo"
    },
    "sender": {"login": "test-user"}
  }'
```

---

## Acceptance Criteria

- [ ] Nodo Write File rimosso
- [ ] Nodo PostgreSQL aggiunto con INSERT query
- [ ] Test curl produce record in ci_status table
- [ ] Discord notification continua a funzionare
- [ ] Error handling mantiene retry policy

---

## Rollback

Se necessario tornare a file-based:
1. Riattivare nodo Write File
2. Disattivare nodo PostgreSQL
3. Claude Code hook ha fallback a file (backward compatible)

---

## Note

- La tabella `ci_status` è nel database `n8n` (stesso DB usato da N8N)
- Il campo `injected` viene settato a TRUE da Claude Code dopo l'injection
- Cleanup automatico: record > 7 giorni vengono eliminati
