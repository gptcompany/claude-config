#!/bin/bash
# System State Snapshot - Capture system configuration for disaster recovery
#
# Usage:
#   ./system-state-snapshot.sh                    # Output to stdout
#   ./system-state-snapshot.sh --save             # Save to timestamped file

set -euo pipefail

SNAPSHOT_DIR="${HOME}/.claude/snapshots"
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
SAVE_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --save) SAVE_MODE=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Create snapshot directory if saving
if [[ "$SAVE_MODE" == "true" ]]; then
    mkdir -p "$SNAPSHOT_DIR"
fi

# Build JSON using jq for proper escaping
generate_snapshot() {
    local hostname=$(hostname)
    local os_name=$(lsb_release -d 2>/dev/null | cut -f2 || echo "Linux")
    local os_version=$(lsb_release -r 2>/dev/null | cut -f2 || echo "unknown")
    local kernel=$(uname -r)
    local arch=$(uname -m)
    local cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d':' -f2 | xargs || echo "unknown")
    local cpu_cores=$(nproc)
    local memory_gb=$(LC_NUMERIC=C awk '/MemTotal/ {printf "%.1f", $2/1024/1024}' /proc/meminfo)
    local docker_version=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "not installed")
    local containers_running=$(docker ps -q 2>/dev/null | wc -l || echo 0)
    local containers_total=$(docker ps -aq 2>/dev/null | wc -l || echo 0)
    local images_count=$(docker images -q 2>/dev/null | wc -l || echo 0)

    # Get running containers as JSON array
    local containers_json=$(docker ps --format '{{.Names}}' 2>/dev/null | jq -R . | jq -s . || echo '[]')

    # Get listening ports as JSON array
    local ports_json=$(ss -tlnp 2>/dev/null | awk 'NR>1 {split($4,a,":"); port=a[length(a)]; if(port~/^[0-9]+$/ && port<65536) print port}' | sort -n | uniq | jq -R 'tonumber' | jq -s . || echo '[]')

    # Get systemd services
    local services_json=$(systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null | awk '{print $1}' | grep -v '@' | head -30 | jq -R . | jq -s . || echo '[]')

    # Get cron jobs
    local cron_json=$(crontab -l 2>/dev/null | grep -v '^#' | grep -v '^$' | jq -R . | jq -s . || echo '[]')

    # Get disk usage
    local disk_root_percent=$(df / --output=pcent 2>/dev/null | tail -1 | tr -d ' %' || echo 0)

    # Get git repos status
    local repos_json='[]'
    for repo in /media/sam/1TB/nautilus_dev /media/sam/1TB/UTXOracle ~/.claude; do
        if [[ -d "$repo/.git" ]]; then
            cd "$repo"
            local branch=$(git branch --show-current 2>/dev/null || echo "unknown")
            local uncommitted=$(git status --porcelain 2>/dev/null | wc -l)
            repos_json=$(echo "$repos_json" | jq --arg path "$repo" --arg branch "$branch" --argjson uncommitted "$uncommitted" '. + [{path: $path, branch: $branch, uncommitted: $uncommitted}]')
        fi
    done

    # Build final JSON
    jq -n \
        --arg timestamp "$(date -Iseconds)" \
        --arg hostname "$hostname" \
        --arg os_name "$os_name" \
        --arg os_version "$os_version" \
        --arg kernel "$kernel" \
        --arg arch "$arch" \
        --arg cpu_model "$cpu_model" \
        --argjson cpu_cores "$cpu_cores" \
        --argjson memory_gb "$memory_gb" \
        --arg docker_version "$docker_version" \
        --argjson containers_running "$containers_running" \
        --argjson containers_total "$containers_total" \
        --argjson images_count "$images_count" \
        --argjson containers "$containers_json" \
        --argjson ports "$ports_json" \
        --argjson services "$services_json" \
        --argjson cron "$cron_json" \
        --argjson disk_root_percent "$disk_root_percent" \
        --argjson repos "$repos_json" \
        '{
            timestamp: $timestamp,
            hostname: $hostname,
            os: {
                name: $os_name,
                version: $os_version,
                kernel: $kernel,
                arch: $arch
            },
            hardware: {
                cpu_model: $cpu_model,
                cpu_cores: $cpu_cores,
                memory_total_gb: $memory_gb
            },
            docker: {
                version: $docker_version,
                containers_running: $containers_running,
                containers_total: $containers_total,
                images: $images_count,
                running_containers: $containers
            },
            network: {
                listening_ports: $ports
            },
            systemd_services: $services,
            cron_jobs: $cron,
            disk_root_percent: $disk_root_percent,
            git_repositories: $repos
        }'
}

# Main execution
SNAPSHOT=$(generate_snapshot)

if [[ "$SAVE_MODE" == "true" ]]; then
    SNAPSHOT_FILE="${SNAPSHOT_DIR}/snapshot_${TIMESTAMP}.json"
    echo "$SNAPSHOT" > "$SNAPSHOT_FILE"
    echo "Snapshot saved to: $SNAPSHOT_FILE" >&2

    # Keep only last 10 snapshots
    ls -t "${SNAPSHOT_DIR}"/snapshot_*.json 2>/dev/null | tail -n +11 | xargs -r rm
else
    echo "$SNAPSHOT"
fi
