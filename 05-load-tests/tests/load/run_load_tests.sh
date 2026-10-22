#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 [--docker|--local] [extra k6 args...]" >&2
    exit 1
}

MODE="docker"
case "${1:-}" in
    --docker) MODE="docker"; shift ;;
    --local) MODE="local"; shift ;;
    -h|--help) usage ;;
esac

pushd "$(dirname "$0")" > /dev/null
trap 'popd > /dev/null' EXIT

PROJECT_ROOT="${PROJECT_ROOT:-$(cd ../.. && pwd)}"
SUMMARY_FILE="${SUMMARY_FILE:-results/summary-$(date +%Y%m%d-%H%M%S).json}"
mkdir -p "$(dirname "$SUMMARY_FILE")"

run_docker() {
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" --profile loadtest \
        run --rm --user "$(id -u):$(id -g)" loadtest run load_test.ts --summary-export="$SUMMARY_FILE" "$@"
}

run_local() {
    local base_url="${BASE_URL:-http://localhost:8000}"
    local data_file="${DATA_FILE:-$PROJECT_ROOT/bl_full_data.csv}"

    if [ ! -f users.json ]; then
        python make_users.py "$data_file" users.json
    fi

    if ! curl -sf "$base_url/health" > /dev/null; then
        echo "API not reachable at $base_url/health - start it with: docker compose up -d api" >&2
        exit 1
    fi

    BASE_URL="$base_url" k6 run load_test.ts --summary-export="$SUMMARY_FILE" "$@"
}

if [ "$MODE" = "docker" ]; then
    run_docker "$@"
else
    run_local "$@"
fi