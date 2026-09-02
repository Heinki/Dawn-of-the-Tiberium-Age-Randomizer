#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

"$script_dir/build_exe_wine.sh" --output "$script_dir/../DTARandomizer.exe"
python3 "$script_dir/Archipelago/build_apworld.py" \
    --output-directory "$script_dir/Archipelago"
