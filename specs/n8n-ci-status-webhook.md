# N8N Workflow Specification: GitHub CI Status Notifier

**Version**: 1.0
**Author**: Claude Code
**Date**: 2026-01-12
**Status**: Ready for Implementation

---

## Overview

Event-driven workflow that receives GitHub workflow completion webhooks and:
1. Notifies Discord channel with CI status
2. Writes status file for Claude Code context injection

## Webhook Configuration

### GitHub Repository Settings

```
URL: https://<n8n-host>/webhook/github-ci-status
Content-Type: application/json
Secret: <generate secure secret>
Events: ☑ Workflow runs
```

### N8N Webhook Node

```yaml
Node: Webhook
HTTP Method: POST
Path: github-ci-status
Authentication: Header Auth
  Header Name: X-Hub-Signature-256
  Header Value: sha256=<hmac of payload with secret>
Response Mode: Last Node
```

---

## Input Schema (GitHub Webhook Payload)

```json
{
  "action": "completed",
  "workflow_run": {
    "id": 123456789,
    "name": "CI",
    "head_branch": "feature/my-feature",
    "head_sha": "abc123def456",
    "status": "completed",
    "conclusion": "success|failure|cancelled|skipped",
    "html_url": "https://github.com/owner/repo/actions/runs/123456789",
    "created_at": "2026-01-12T10:00:00Z",
    "updated_at": "2026-01-12T10:05:00Z",
    "run_started_at": "2026-01-12T10:00:00Z",
    "pull_requests": [
      {
        "number": 42,
        "url": "https://api.github.com/repos/owner/repo/pulls/42"
      }
    ]
  },
  "repository": {
    "name": "repo-name",
    "full_name": "owner/repo-name",
    "html_url": "https://github.com/owner/repo-name"
  },
  "sender": {
    "login": "username"
  }
}
```

---

## Processing Logic

### Step 1: Filter Node

Only process completed workflow runs:

```javascript
// Filter condition
$json.action === "completed" &&
$json.workflow_run.status === "completed"
```

### Step 2: Transform Node

Extract and normalize data:

```javascript
// Code node
const run = $json.workflow_run;
const repo = $json.repository;

const conclusion = run.conclusion;
const isSuccess = conclusion === "success";
const isFailed = conclusion === "failure";

// Get PR number if exists
const prNumber = run.pull_requests?.[0]?.number || null;
const prUrl = prNumber
  ? `${repo.html_url}/pull/${prNumber}`
  : null;

// Calculate duration
const startTime = new Date(run.run_started_at);
const endTime = new Date(run.updated_at);
const durationMs = endTime - startTime;
const durationMin = Math.round(durationMs / 60000);

return {
  // Identifiers
  run_id: run.id,
  repo: repo.full_name,
  repo_name: repo.name,
  branch: run.head_branch,
  commit_sha: run.head_sha.substring(0, 8),

  // Status
  conclusion: conclusion,
  is_success: isSuccess,
  is_failed: isFailed,

  // PR info
  pr_number: prNumber,
  pr_url: prUrl,

  // URLs
  run_url: run.html_url,
  repo_url: repo.html_url,

  // Timing
  duration_min: durationMin,
  completed_at: run.updated_at,

  // Actor
  triggered_by: $json.sender.login,

  // For Discord
  emoji: isSuccess ? "✅" : isFailed ? "❌" : "⚠️",
  status_text: isSuccess ? "PASSED" : isFailed ? "FAILED" : conclusion.toUpperCase()
};
```

### Step 3: Discord Notification Node

```yaml
Node: Discord (Webhook)
Webhook URL: {{ $env.DISCORD_WEBHOOK_URL }}
```

**Message Format:**

```javascript
// Message content
const d = $json;

const embed = {
  title: `${d.emoji} CI ${d.status_text}: ${d.repo_name}`,
  color: d.is_success ? 0x28a745 : d.is_failed ? 0xdc3545 : 0xffc107,
  fields: [
    {
      name: "Branch",
      value: d.branch,
      inline: true
    },
    {
      name: "Commit",
      value: d.commit_sha,
      inline: true
    },
    {
      name: "Duration",
      value: `${d.duration_min} min`,
      inline: true
    }
  ],
  url: d.run_url,
  timestamp: d.completed_at
};

// Add PR field if exists
if (d.pr_number) {
  embed.fields.push({
    name: "Pull Request",
    value: `[#${d.pr_number}](${d.pr_url})`,
    inline: true
  });

  // Add merge hint for success
  if (d.is_success) {
    embed.fields.push({
      name: "Action",
      value: "Ready to merge!",
      inline: true
    });
  }
}

return {
  embeds: [embed]
};
```

### Step 4: Write Status File (SSH/Local)

Write to Claude Code metrics directory for context injection.

**Option A: Local (if N8N on same machine)**

```yaml
Node: Write Binary File
File Path: /home/sam/.claude/metrics/ci_status.json
```

**Option B: SSH (if N8N remote)**

```yaml
Node: SSH
Host: {{ $env.DEV_MACHINE_HOST }}
Command: |
  cat > ~/.claude/metrics/ci_status.json << 'EOF'
  {{ JSON.stringify($json.status_payload) }}
  EOF
```

**Status File Schema:**

```json
{
  "repo": "owner/repo-name",
  "branch": "feature/my-feature",
  "pr_number": 42,
  "pr_url": "https://github.com/owner/repo/pull/42",
  "conclusion": "success",
  "is_success": true,
  "run_url": "https://github.com/owner/repo/actions/runs/123",
  "completed_at": "2026-01-12T10:05:00Z",
  "message": "CI passed, ready to merge",
  "pending_action": "merge"
}
```

**Message Logic:**

```javascript
let message, pending_action;

if ($json.is_success && $json.pr_number) {
  message = `CI passed on PR #${$json.pr_number}, ready to merge`;
  pending_action = "merge";
} else if ($json.is_success) {
  message = `CI passed on ${$json.branch}`;
  pending_action = null;
} else if ($json.is_failed) {
  message = `CI failed on ${$json.branch} - check logs`;
  pending_action = "fix";
} else {
  message = `CI ${$json.conclusion} on ${$json.branch}`;
  pending_action = null;
}

return {
  status_payload: {
    repo: $json.repo,
    branch: $json.branch,
    pr_number: $json.pr_number,
    pr_url: $json.pr_url,
    conclusion: $json.conclusion,
    is_success: $json.is_success,
    run_url: $json.run_url,
    completed_at: $json.completed_at,
    message: message,
    pending_action: pending_action
  }
};
```

---

## Error Handling

### Retry Policy

```yaml
Retry on Fail: true
Max Retries: 3
Wait Between Retries: 1000ms
```

### Error Notification

On workflow error, notify Discord with error details:

```javascript
// Error handler node
return {
  embeds: [{
    title: "⚠️ N8N CI Notifier Error",
    color: 0xff0000,
    description: `Failed to process GitHub webhook: ${$json.error.message}`,
    timestamp: new Date().toISOString()
  }]
};
```

---

## Environment Variables Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DISCORD_WEBHOOK_URL` | Discord channel webhook | `https://discord.com/api/webhooks/...` |
| `GITHUB_WEBHOOK_SECRET` | Shared secret for signature verification | `<random 32+ char string>` |
| `DEV_MACHINE_HOST` | SSH host for status file (if remote) | `sam@192.168.1.x` |
| `DEV_MACHINE_KEY` | SSH key path (if remote) | `/path/to/key` |

---

## Testing

### Test Payload (Success)

```json
{
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
    "full_name": "test/test-repo",
    "html_url": "https://github.com/test/test-repo"
  },
  "sender": {"login": "test-user"}
}
```

### Test Payload (Failure)

```json
{
  "action": "completed",
  "workflow_run": {
    "id": 999999998,
    "name": "CI",
    "head_branch": "broken-branch",
    "head_sha": "def456abc789",
    "status": "completed",
    "conclusion": "failure",
    "html_url": "https://github.com/test/repo/actions/runs/998",
    "created_at": "2026-01-12T11:00:00Z",
    "updated_at": "2026-01-12T11:05:00Z",
    "run_started_at": "2026-01-12T11:00:00Z",
    "pull_requests": []
  },
  "repository": {
    "name": "test-repo",
    "full_name": "test/test-repo",
    "html_url": "https://github.com/test/test-repo"
  },
  "sender": {"login": "test-user"}
}
```

### Acceptance Criteria

- [ ] Webhook receives GitHub events correctly
- [ ] Signature validation works (reject invalid signatures)
- [ ] Discord notification sent within 5 seconds
- [ ] Status file written to correct path
- [ ] Success/failure messages are correct
- [ ] PR link included when available
- [ ] Duration calculated correctly
- [ ] Retry works on transient failures
- [ ] Error notification sent on workflow failure

---

## Workflow Diagram

```
┌─────────────────┐
│ GitHub Webhook  │
│ workflow_run    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Webhook Node    │
│ + Signature     │
│   Validation    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Filter Node     │
│ action=completed│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Transform Node  │
│ Extract data    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌─────────────┐
│Discord│ │Write Status │
│Notify │ │File (SSH)   │
└───────┘ └─────────────┘
```

---

## Delivery

After implementation, provide:
1. Exported N8N workflow JSON
2. List of credentials to configure
3. Test results screenshot

---

## Contact

Questions: Ask in #n8n-dev channel or ping @sam
