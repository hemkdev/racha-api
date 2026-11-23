#!/usr/bin/env bash
# Database dump, encrypted to the maintainer's public key and sent to Cloudflare R2.
#   backup.sh daily          from cron; pings healthchecks.io when done
#   backup.sh deploy <tag>   from the deploy, before migrating
# The age private key never lives on the VM: nothing leaves here that this machine can read.
set -euo pipefail
cd "$(dirname "$0")"
set -a
# shellcheck source=/dev/null
. ./.env
set +a

now=$(date -u +%Y-%m-%dT%H%M%SZ)
case "${1:-}" in
  daily) key="racha/daily/$now.sql.gz.age" ;;
  deploy) key="racha/deploy/${2:?missing tag}-$now.sql.gz.age" ;;
  *) echo "usage: backup.sh daily | backup.sh deploy <tag>" >&2; exit 2 ;;
esac

mkdir -p backups
file="backups/${key//\//-}"
docker compose exec -T db pg_dump -U racha -d racha | gzip | age -r "$AGE_RECIPIENT" > "$file"

# R2 speaks the S3 API. aws-cli runs in a container so nothing gets installed on the VM;
# credentials go through the environment, never the command line.
export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
docker run --rm -q -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION=auto \
  -v "$PWD/backups:/backups:ro" docker.io/amazon/aws-cli:2.17.0 \
  s3 cp "/$file" "s3://$R2_BUCKET/$key" --endpoint-url "$R2_ENDPOINT" --only-show-errors

# The local copy is for a quick restore; the bucket's retention is the real one.
find backups -name '*.age' -mtime +7 -delete

if [ "$1" = daily ] && [ -n "${BACKUP_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 -o /dev/null "$BACKUP_PING_URL"
fi
