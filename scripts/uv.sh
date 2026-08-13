#!/usr/bin/env sh
set -eu

if command -v uv >/dev/null 2>&1; then
  exec uv "$@"
fi

if command -v uv.cmd >/dev/null 2>&1; then
  exec uv.cmd "$@"
fi

if [ -n "${USERPROFILE:-}" ] && command -v cygpath >/dev/null 2>&1; then
  user_profile_path="$(cygpath -u "$USERPROFILE")"
  if [ -f "$user_profile_path/.local/bin/uv.cmd" ]; then
    exec "$user_profile_path/.local/bin/uv.cmd" "$@"
  fi
fi

echo "ERROR: uv is required for development commands. Install uv before continuing." >&2
exit 1
