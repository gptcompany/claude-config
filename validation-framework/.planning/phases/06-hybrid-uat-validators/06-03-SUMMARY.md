# Plan 06-03: Security Scanning Templates (Trivy)

## Status: COMPLETED

## Objective

Create security scanning templates using Trivy for container and dependency vulnerability scanning, with SARIF output for GitHub Security tab integration.

## Files Created

### 1. Trivy Configuration Template
**Path:** `~/.claude/templates/validation/validators/security/trivy.yaml.j2`

Comprehensive Trivy configuration with:
- Configurable scan types (vuln, secret, misconfig)
- Severity filtering (default: CRITICAL, HIGH)
- Ignore unfixed vulnerabilities option
- SARIF output format for GitHub integration
- Cache and database settings
- Filesystem exclusions (node_modules, .git, vendor, etc.)
- Exit code 1 for PR blocking

### 2. Trivyignore Template
**Path:** `~/.claude/templates/validation/validators/security/.trivyignore.j2`

Documented ignore file template with:
- Proper CVE documentation format
- Justification requirements
- Review date tracking
- Ticket/issue reference support
- Sections for:
  - Vulnerability ignores
  - Secret ignores
  - Misconfiguration ignores
- Review log tracking

### 3. Security Workflow Template
**Path:** `~/.claude/templates/validation/ci/security.yml.j2`

GitHub Actions workflow with multiple scan jobs:

| Job | Description | Trigger |
|-----|-------------|---------|
| `dependency-scan` | Filesystem vuln scan | All events |
| `container-scan` | Docker image scan | If Dockerfile exists |
| `secret-scan` | Secret detection | All events |
| `misconfig-scan` | IaC config scan | If enabled |
| `sbom-generation` | CycloneDX SBOM | Main branch only |
| `security-summary` | Aggregated results | Always |

## Jinja2 Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `project_name` | (required) | Project identifier |
| `severity` | `CRITICAL,HIGH` | Minimum severity to report |
| `ignore_unfixed` | `true` | Skip unfixed vulnerabilities |
| `scan_types` | `['vuln', 'secret']` | Scanners to enable |
| `image_name` | `app` | Docker image name |
| `trivyignore_path` | (optional) | Custom ignore file path |
| `ignored_cves` | (optional) | List of CVEs to ignore |
| `ignored_secrets` | (optional) | Secret patterns to ignore |
| `ignored_misconfigs` | (optional) | Misconfig IDs to ignore |

## Key Features

### PR Blocking
- **CRITICAL**: `exit-code: '1'` is set on all scan jobs
- Failed scans will block PR merge via required status checks
- Summary job aggregates results and fails if any scan fails

### GitHub Security Integration
- All scan results uploaded as SARIF to GitHub Security tab
- Separate categories for each scan type:
  - `trivy-filesystem`
  - `trivy-container`
  - `trivy-secrets`
  - `trivy-misconfig`

### Scheduled Scans
- Daily scan at 2 AM UTC for continuous monitoring
- Catches newly disclosed CVEs affecting existing code

### SBOM Generation
- CycloneDX format for compliance
- Only on main/master branch pushes
- 90-day artifact retention

## Usage Example

```yaml
# In project's validation config
security:
  trivy:
    severity: "CRITICAL,HIGH"
    ignore_unfixed: true
    scan_types:
      - vuln
      - secret
      - misconfig
    image_name: "myapp"
```

## Testing Recommendations

1. **Template Rendering**: Verify Jinja2 renders correctly with various inputs
2. **Workflow Syntax**: Run `actionlint` on rendered workflow
3. **Trivy Config**: Validate with `trivy config --config-file trivy.yaml`
4. **SARIF Output**: Ensure proper upload to GitHub Security tab

## Dependencies

- `aquasecurity/trivy-action@master`
- `github/codeql-action/upload-sarif@v3`
- `docker/setup-buildx-action@v3` (for container scans)
- `docker/build-push-action@v6` (for container scans)

## Security Considerations

- Workflow has minimal permissions (contents: read, security-events: write)
- No secrets exposed in logs
- Trivyignore requires documented justification for audit trail
- Review dates encourage periodic re-evaluation of ignored CVEs
