# Configure Coding Standards

Manage coding standards enforcement settings.

## Configuration File

`~/.claude/standards-config.json`

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable standards checking |
| `mode` | string | `"warn"` | Enforcement mode: `warn`, `block`, `off` |
| `excludePaths` | array | see below | Paths to ignore |

## Default Exclude Paths

```json
[
  "node_modules",
  "dist",
  "build",
  ".git",
  "vendor",
  "venv",
  ".venv",
  "__pycache__",
  ".next",
  "coverage",
  ".claude/checkpoints"
]
```

## Modes

| Mode | Behavior |
|------|----------|
| `warn` | Show warnings but allow all writes |
| `block` | Block writes with error-level issues |
| `off` | Disable standards checking entirely |

## Example Configuration

```json
{
  "enabled": true,
  "mode": "block",
  "excludePaths": ["node_modules", "dist", "vendor", "generated/"]
}
```

## Quick Commands

### Enable Block Mode
```bash
echo '{"enabled":true,"mode":"block"}' > ~/.claude/standards-config.json
```

### Disable Temporarily
```bash
echo '{"enabled":false}' > ~/.claude/standards-config.json
```

### Add Custom Exclusion
```bash
# Read current config, add path, write back
node -e "
const fs = require('fs');
const p = '$HOME/.claude/standards-config.json';
let c = {};
try { c = JSON.parse(fs.readFileSync(p)); } catch {}
c.excludePaths = c.excludePaths || [];
c.excludePaths.push('my-generated/');
fs.writeFileSync(p, JSON.stringify(c, null, 2));
"
```

## When to Use Each Mode

- **warn** (default): During active development, see issues without blocking
- **block**: Before commits/PRs, enforce strict compliance
- **off**: When working with generated code or third-party integrations

## Related Commands

- `/standards:check` - Manually check files against standards
