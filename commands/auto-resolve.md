# Auto-Resolve Drift Issues

Analyze and resolve configuration drift issues automatically.

## Usage

```
/auto-resolve                   # List all issues with resolution plans
/auto-resolve DRIFT-001         # Execute resolution for specific issue
/auto-resolve --dry-run         # Preview without executing
/auto-resolve --create-issues   # Create GitHub issues for tracking
```

## Process

1. **Analyze**: Run drift-detector to find issues
2. **Plan**: Generate resolution plans for each issue
3. **Review**: Present plans for user approval
4. **Execute**: Apply approved fixes

## Issue Categories

| Category | Auto-Resolvable | Risk |
|----------|-----------------|------|
| duplicate_skill | Yes | Low |
| duplicate_command | Yes | Low |
| obsolete_file | Yes | Low |
| missing_file | Yes | Low |
| settings_drift | Partial | Medium |
| port_conflict | No | High |
| service_down | Yes | Medium |

## Instructions

When user runs this command:

1. **List Mode** (no arguments):
   - Run `python3 ~/.claude/scripts/issue-resolver.py`
   - Display all issues with their resolution plans
   - Highlight which are auto-resolvable

2. **Execute Mode** (with issue ID):
   - First run with `--dry-run` to preview
   - Ask user for confirmation
   - If approved, execute without `--dry-run`
   - Report results

3. **Create Issues Mode**:
   - Run with `--create-issues`
   - Create GitHub issues for each drift issue
   - Include resolution plan in issue body

## Example Output

```
Issue Resolution Analysis
==================================================
Total Issues: 3
Auto-Resolvable: 2

DRIFT-001 [AUTO] [HIGH]
  Duplicate skill 'pytest-test-generator' found in nautilus_dev
  Fix Commands:
    - rm -rf /media/sam/1TB/nautilus_dev/.claude/skills/pytest-test-generator

DRIFT-002 [MANUAL] [MEDIUM]
  Port 9000 conflict detected
  Manual Steps:
    - Identify which service should use the port
    - Stop or reconfigure the conflicting service
```

## Safety

- All destructive commands are logged
- Git recovery is possible for deleted files
- High-risk operations require explicit confirmation
- `--dry-run` always available for preview
