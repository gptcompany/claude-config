# Check Coding Standards

Manually check a file or directory against coding standards.

## Usage

Specify a file path to check:
```
/standards:check path/to/file.js
```

Or check multiple files:
```
/standards:check src/
```

## On Invocation

```bash
# Check specified file or directory
node ~/.claude/scripts/hooks/skills/standards/check-file.js "$ARGUMENTS"
```

## Checks Performed

### JavaScript/TypeScript
- **console.log in production code** - Remove or use logger
- **`any` type usage** - Use specific types
- **Hardcoded secrets** - Use environment variables
- **TODOs without issue links** - Link to issue tracker
- **debugger statements** - Remove before committing
- **alert() calls** - Use proper UI feedback
- **process.exit() in library code** - Throw errors instead

### Python
- **print() statements** - Use logging module
- **Bare except clauses** - Specify exception type
- **Star imports** - Use explicit imports
- **Hardcoded secrets** - Use environment variables
- **Mutable default arguments** - Use None and check in body
- **Silent exception handling** - At least log exceptions

## Output

Lists all issues found with line numbers and severity:
- **ERROR** - Must fix before proceeding
- **WARN** - Should fix, but not blocking
- **INFO** - Suggestions for improvement

## Examples

```bash
# Check single file
/standards:check src/utils/api.js

# Check entire directory
/standards:check lib/

# Quick check before commit
/standards:check $(git diff --name-only HEAD)
```

## Configuration

See `/standards:config` to configure enforcement mode and exclusions.
