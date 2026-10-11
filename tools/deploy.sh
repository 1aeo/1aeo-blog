#!/usr/bin/env bash
# Deploy site/ to the 1aeo.com web server. Dry run by default; pass --apply to copy.
# Compares by checksum, never deletes anything on the server, and leaves permissions alone.
# Needs an SSH alias for the server (default "do1aeo"; override with DEPLOY_HOST).
set -euo pipefail
HOST="${DEPLOY_HOST:-do1aeo}"
DEST="${DEPLOY_ROOT:-/var/www/1aeo.com/html}"
cd "$(dirname "$0")/.."
MODE=(--dry-run)
if [[ "${1:-}" == "--apply" ]]; then MODE=(); fi
rsync -rlci "${MODE[@]}" site/blog/ "$HOST:$DEST/blog/"
rsync -rlci "${MODE[@]}" site/sitemap.xml "$HOST:$DEST/sitemap.xml"
if [[ ${#MODE[@]} -gt 0 ]]; then echo "Dry run: the lines above would change. Re-run with --apply to deploy."; fi
