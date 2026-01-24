# Phase 14: Hooks Node.js Port - Research

**Researched:** 2026-01-24
**Domain:** Node.js cross-platform CLI hooks system
**Confidence:** HIGH

<research_summary>
## Summary

Researched the Node.js ecosystem for building a cross-platform hooks system, using ECC (everything-claude-code) as the reference implementation. ECC already has a mature Node.js hook architecture with:
- Declarative `hooks.json` configuration
- Shared `utils.js` library with cross-platform helpers
- Plugin-style hook events (PreToolUse, PostToolUse, SessionStart, SessionEnd, etc.)

The standard approach is pure Node.js with minimal dependencies. ECC uses only built-in Node.js modules (fs, path, os, child_process) for maximum portability. For more complex CLI needs, the ecosystem provides execa (process execution), commander (arg parsing), and zx (shell scripting).

**Primary recommendation:** Port ECC's utils.js and hooks.json pattern directly. Use Node.js built-ins for file/process operations. Add execa only if complex subprocess piping is needed.
</research_summary>

<standard_stack>
## Standard Stack

### Core (What ECC Uses)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Node.js built-ins | - | fs, path, os, child_process | Zero dependencies, cross-platform |
| None external | - | ECC uses no npm dependencies | Maximum portability |

### Supporting (If Needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| execa | 9.x | Process execution | Complex subprocess piping, better error handling |
| zx | 8.x | Shell scripting | When you need shell-like scripting convenience |
| commander | 12.x | CLI arg parsing | If hooks need complex CLI options |
| chalk | 5.x | Colored output | Better terminal UX (optional) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Node.js child_process | execa | execa has better Windows support, but adds dependency |
| Manual JSON parsing | cosmiconfig | cosmiconfig for complex config discovery, overkill for hooks.json |
| Bash scripts | zx | zx for complex shell ops, but ECC pattern is simpler |

**Installation (minimal):**
```bash
# No dependencies needed - ECC pattern uses pure Node.js
node scripts/hooks/session-start.js

# If execa needed for complex cases:
npm install execa
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure (from ECC)
```
~/.claude/
├── hooks/
│   └── hooks.json           # Declarative hook configuration
└── scripts/
    ├── hooks/
    │   ├── session-start.js  # SessionStart hook
    │   ├── session-end.js    # SessionEnd hook
    │   ├── pre-compact.js    # PreCompact hook
    │   └── suggest-compact.js # PreToolUse hook
    └── lib/
        ├── utils.js          # Cross-platform utilities
        └── package-manager.js # Package manager detection
```

### Pattern 1: Declarative hooks.json
**What:** Define hooks in JSON, not code. Each hook specifies matcher, command, and description.
**When to use:** Always - this is the Claude Code standard.
**Example:**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "tool == \"Edit\" || tool == \"Write\"",
        "hooks": [
          {
            "type": "command",
            "command": "node \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/suggest-compact.js\""
          }
        ],
        "description": "Suggest manual compaction at logical intervals"
      }
    ]
  }
}
```

### Pattern 2: Shared Utils Library (from ECC)
**What:** Central utils.js with cross-platform file/process operations
**When to use:** For all file, path, and process operations
**Example:**
```javascript
// From ECC scripts/lib/utils.js
const path = require('path');
const os = require('os');
const fs = require('fs');

// Platform detection
const isWindows = process.platform === 'win32';
const isMacOS = process.platform === 'darwin';
const isLinux = process.platform === 'linux';

// Cross-platform command check
function commandExists(cmd) {
  try {
    if (isWindows) {
      execSync(`where ${cmd}`, { stdio: 'pipe' });
    } else {
      execSync(`which ${cmd}`, { stdio: 'pipe' });
    }
    return true;
  } catch {
    return false;
  }
}
```

### Pattern 3: Hook I/O Protocol
**What:** Hooks receive JSON on stdin, output to stderr (user-visible) and stdout (return to Claude)
**When to use:** For all hook implementations
**Example:**
```javascript
async function readStdinJson() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => data += chunk);
    process.stdin.on('end', () => {
      resolve(data.trim() ? JSON.parse(data) : {});
    });
  });
}

// User-visible message
function log(message) { console.error(message); }

// Return to Claude
function output(data) { console.log(JSON.stringify(data)); }
```

### Pattern 4: Graceful Degradation
**What:** Hooks should never block on errors - log and exit 0
**When to use:** Always - hooks must not break the workflow
**Example:**
```javascript
main().catch(err => {
  console.error('[Hook] Error:', err.message);
  process.exit(0); // Don't block on errors
});
```

### Anti-Patterns to Avoid
- **Inline node -e scripts:** ECC uses these for simple hooks, but they're hard to maintain. Use separate .js files for anything complex.
- **Shell commands in hooks:** Avoid `rm`, `cp`, `find` - use Node.js fs module.
- **Assuming Unix paths:** Always use `path.join()`, never string concatenation.
- **Blocking on errors:** Hooks must `exit(0)` even on failure.
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Path joining | String concatenation | `path.join()` | Windows uses backslash |
| Home directory | `process.env.HOME` | `os.homedir()` | Works on Windows |
| Command exists check | Custom which/where | Node.js `commandExists()` pattern | Platform-specific |
| File globbing | Manual recursion | `glob` or Node.js pattern | Edge cases in symlinks, permissions |
| JSON config | Manual parsing | Native JSON.parse() is fine | But consider cosmiconfig for discovery |
| Process execution | `child_process.exec` | `child_process.execSync` or execa | Sync is simpler for hooks |

**Key insight:** ECC's utils.js already solved cross-platform file operations. Port it directly rather than reimplementing.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Path Separator Issues
**What goes wrong:** Paths break on Windows (uses \ not /)
**Why it happens:** String concatenation instead of path.join()
**How to avoid:** Always use `path.join()` for paths, `path.sep` if needed
**Warning signs:** Works on Linux, fails on Windows

### Pitfall 2: Shell Command Differences
**What goes wrong:** `which`, `rm -rf`, `cp` don't exist on Windows
**Why it happens:** Assuming Unix shell commands
**How to avoid:** Use Node.js fs module or cross-platform npm packages (rimraf)
**Warning signs:** "command not found" on Windows

### Pitfall 3: Environment Variables
**What goes wrong:** `$HOME` doesn't work on Windows
**Why it happens:** Windows uses `%USERPROFILE%`
**How to avoid:** Use `os.homedir()`, `process.env` with fallbacks
**Warning signs:** Config files not found on Windows

### Pitfall 4: Line Endings
**What goes wrong:** Scripts fail with `\r\n` issues
**Why it happens:** Windows uses CRLF, Unix uses LF
**How to avoid:** Use `.gitattributes` with `* text=auto`, normalize in code
**Warning signs:** "bad interpreter" errors, JSON parse failures

### Pitfall 5: Hook Blocking
**What goes wrong:** Hook error blocks entire Claude workflow
**Why it happens:** Exit code 1 on error
**How to avoid:** Always exit(0), log errors to stderr
**Warning signs:** Claude gets stuck, user must kill session
</common_pitfalls>

<code_examples>
## Code Examples

### Cross-Platform Utils (from ECC)
```javascript
// Source: /media/sam/1TB/everything-claude-code/scripts/lib/utils.js
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

const isWindows = process.platform === 'win32';

function getHomeDir() { return os.homedir(); }
function getClaudeDir() { return path.join(getHomeDir(), '.claude'); }

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
  return dirPath;
}

function findFiles(dir, pattern, options = {}) {
  const { maxAge = null, recursive = false } = options;
  const results = [];
  // ... cross-platform file finding
  return results;
}
```

### Hook I/O Pattern
```javascript
// Source: ECC hooks pattern
async function main() {
  // Read input from Claude
  const input = await readStdinJson();
  const toolName = input.tool_name;
  const toolInput = input.tool_input;

  // Do validation/processing
  if (shouldBlock(toolInput)) {
    log('[Hook] BLOCKED: ' + reason);
    output({ decision: 'block', reason: reason });
    process.exit(1);
  }

  // Pass through
  output(input);
  process.exit(0);
}

main().catch(err => {
  console.error('[Hook] Error:', err.message);
  process.exit(0); // Don't block on errors
});
```

### hooks.json Schema
```javascript
// Source: Claude Code hooks reference
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "tool == \"Bash\" && tool_input.command matches \"git push\"",
        "hooks": [{ "type": "command", "command": "node script.js" }],
        "description": "Review before git push"
      }
    ],
    "PostToolUse": [...],
    "SessionStart": [...],
    "SessionEnd": [...]
  }
}
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bash/Python hooks | Node.js hooks | 2025 | Cross-platform reliability |
| Manual path handling | path.join() always | Long-standing | Standard practice |
| exec() async | execSync() for hooks | Hooks are sync | Simpler hook logic |
| Shell commands | Node.js fs module | Best practice | No shell dependency |

**New tools/patterns to consider:**
- **Input modification (v2.0.10+):** PreToolUse hooks can now modify tool inputs, not just block
- **PermissionRequest event (v2.0.45+):** Hook into permission decisions
- **SubagentStop event (v1.0.41+):** Hook when subagents finish
- **execa v9:** Major improvements for Windows, ESM-first

**Deprecated/outdated:**
- **npm uninstall hooks:** Removed in npm v7+, need explicit cleanup
- **process.env.HOME:** Use os.homedir() instead
- **String path concatenation:** Always use path.join()
</sota_updates>

<ecc_reference>
## ECC Implementation Reference

**Location:** `/media/sam/1TB/everything-claude-code/`

### Key Files to Port
| ECC File | Purpose | Priority |
|----------|---------|----------|
| `hooks/hooks.json` | Declarative hook config | HIGH |
| `scripts/lib/utils.js` | Cross-platform utilities (368 LOC) | HIGH |
| `scripts/lib/package-manager.js` | Package manager detection | MEDIUM |
| `scripts/hooks/session-start.js` | Session initialization | HIGH |
| `scripts/hooks/session-end.js` | Session cleanup | HIGH |
| `scripts/hooks/suggest-compact.js` | Compaction suggestion | MEDIUM |
| `scripts/hooks/pre-compact.js` | Pre-compaction state save | MEDIUM |
| `scripts/hooks/evaluate-session.js` | Session pattern extraction | LOW |

### ECC Hook Events Used
- PreToolUse: Dev server blocking, tmux reminder, git push review, doc file blocking
- PostToolUse: PR URL logging, Prettier formatting, TypeScript check, console.log warning
- PreCompact: State saving before compaction
- SessionStart: Load previous context, detect package manager
- SessionEnd: Persist session state, evaluate patterns
- Stop: Check for console.log in modified files

### utils.js Functions to Port
- Directory helpers: `getHomeDir`, `getClaudeDir`, `getSessionsDir`, `ensureDir`
- File operations: `findFiles`, `readFile`, `writeFile`, `appendFile`
- Git operations: `isGitRepo`, `getGitModifiedFiles`
- Hook I/O: `readStdinJson`, `log`, `output`
- System: `commandExists`, `runCommand`
</ecc_reference>

<open_questions>
## Open Questions

1. **Windows CI Testing**
   - What we know: ECC claims cross-platform support
   - What's unclear: How thoroughly tested on Windows?
   - Recommendation: Add Windows to CI matrix in Plan 14-05

2. **Hook Timeout Handling**
   - What we know: hooks.json supports `timeout` field
   - What's unclear: What happens on timeout? How to handle gracefully?
   - Recommendation: Research during planning, test with slow hooks

3. **ESM vs CommonJS**
   - What we know: ECC uses CommonJS (require)
   - What's unclear: Should we modernize to ESM?
   - Recommendation: Stick with CommonJS for Node.js 18+ compatibility
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- ECC `hooks/hooks.json` - Full declarative hook configuration
- ECC `scripts/lib/utils.js` - 368 LOC of cross-platform utilities
- ECC `scripts/hooks/*.js` - Working hook implementations
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks) - Official hooks documentation

### Secondary (MEDIUM confidence)
- [Node.js CLI Apps Best Practices](https://github.com/lirantal/nodejs-cli-apps-best-practices) - Cross-platform guidance
- [awesome-cross-platform-nodejs](https://github.com/bcoe/awesome-cross-platform-nodejs) - Library recommendations
- Context7: /sindresorhus/execa - Process execution docs
- Context7: /google/zx - Shell scripting docs

### Tertiary (LOW confidence - needs validation)
- None - all findings verified against ECC implementation
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Node.js built-ins (fs, path, os, child_process)
- Ecosystem: execa, zx, commander (optional)
- Patterns: Declarative hooks.json, shared utils library, I/O protocol
- Pitfalls: Path separators, shell commands, line endings

**Confidence breakdown:**
- Standard stack: HIGH - ECC is production reference
- Architecture: HIGH - ECC patterns verified
- Pitfalls: HIGH - Documented in Node.js CLI best practices
- Code examples: HIGH - Direct from ECC source

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - Node.js ecosystem stable)
</metadata>

---

*Phase: 14-hooks-nodejs-port*
*Research completed: 2026-01-24*
*Ready for planning: yes*
