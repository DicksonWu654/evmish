#!/usr/bin/env sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
case ${1:-} in
  -h|--help)
    printf 'Usage: ./probes/run.sh [YYYY-MM-DD] [--chains chain,chain] [--workers N]\n'
    exit 0
    ;;
esac
case ${1:-} in
  ''|-*) run_date=$(date -u +%F) ;;
  *) run_date=$1; shift ;;
esac
python3 "$repo_dir/probes/run_creation_probes.py" "$run_date" "$@"
python3 "$repo_dir/probes/run_gas_schedule.py" --date "$run_date" "$@"
python3 "$repo_dir/probes/run_value_call.py" --date "$run_date" "$@"
python3 "$repo_dir/probes/run_precompile_sweep.py" --date "$run_date" "$@"
python3 "$repo_dir/probes/build_precompile_matrix.py" --date "$run_date"
python3 "$repo_dir/probes/run_lifecycle_sweep.py" --date "$run_date" "$@"
python3 "$repo_dir/probes/build_lifecycle_matrix.py" --date "$run_date"
