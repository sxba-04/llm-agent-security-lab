#!/usr/bin/env bash
set -euo pipefail

# The x64 runner's Ubuntu sources use mirror+file:/etc/apt/apt-mirrors.txt.
# Lower priority numbers win. Keep the slow Azure endpoint as a fallback
# after Canonical's signed main and security archives.
mirror_list=${1:-/etc/apt/apt-mirrors.txt}
if [[ -f "$mirror_list" ]] &&
   grep -Eq '^https://archive\.ubuntu\.com/ubuntu/[[:blank:]]+priority:2$' "$mirror_list" &&
   grep -Eq '^http://azure\.archive\.ubuntu\.com/ubuntu/[[:blank:]]+priority:1$' "$mirror_list"; then
  sed -i -E 's|^(http://azure\.archive\.ubuntu\.com/ubuntu/[[:blank:]]+)priority:1$|\1priority:4|' "$mirror_list"
  echo 'Ubuntu archive preferred for Playwright dependencies.'
fi
