#!/usr/bin/env bash
set -euo pipefail

# The x64 runner's Ubuntu sources use mirror+file:/etc/apt/apt-mirrors.txt.
# Keep both official HTTPS sources and all unrelated mirrors and metadata.
mirror_list=${1:-/etc/apt/apt-mirrors.txt}
if [[ -f "$mirror_list" ]] &&
   grep -Eq '^https://archive\.ubuntu\.com/ubuntu/([[:blank:]]+priority:[0-9]+)?[[:blank:]]*$' "$mirror_list" &&
   grep -Eq '^https://security\.ubuntu\.com/ubuntu/([[:blank:]]+priority:[0-9]+)?[[:blank:]]*$' "$mirror_list"; then
  # Match the transport and the entire Azure archive entry independently.
  sed -i -E '\|^[[:alpha:]]+://azure\.archive\.ubuntu\.com/ubuntu/([[:blank:]]+priority:[0-9]+)?[[:blank:]]*$| {
    /^http:/d
  }' "$mirror_list"
fi
