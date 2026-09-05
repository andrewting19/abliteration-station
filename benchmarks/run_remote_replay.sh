#!/usr/bin/env bash
# Run on Kevin. Save the summary on the controller, not only on the worker.
set -euo pipefail
host=${1:?Host required}
port=${2:?SSH port required}
instance=${3:?Instance ID required}
helper=${4:?Remote replay helper required}
capture=${5:?Remote capture required}
output=${6:?New local summary path required}
deadline=${7:?Cleanup deadline in Unix seconds required}
[[ "$deadline" =~ ^[0-9]+$ ]] || exit 2
remaining=$((deadline - $(date +%s)))
if (( remaining < 600 )); then
  echo "Replay requires at least 600 seconds before cleanup; remaining: $remaining" >&2
  exit 2
fi
[[ "$host" =~ ^[a-zA-Z0-9.-]+$ && "$port" =~ ^[0-9]+$ && "$instance" =~ ^[0-9]+$ ]] || exit 2
[[ "$helper" =~ ^/[a-zA-Z0-9_./-]+$ && "$capture" =~ ^/[a-zA-Z0-9_./-]+$ ]] || exit 2
[[ ! -e "$output" && -d "$(dirname -- "$output")" ]] || exit 2
umask 077
set -o noclobber
ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=2 -o StrictHostKeyChecking=accept-new \
  -o "HostKeyAlias=vast-instance-$instance" \
  -i "${QWEN38_SSH_KEY:-/root/.ssh/abliteration-station-vast}" -p "$port" "root@$host" \
  "python3 '$helper' '$capture' --stream --base-url http://127.0.0.1:17070 --api-key-file /workspace/qwen38/api_key --max-tokens 4096 --seed 424242" \
  > "$output"
python3 - "$output" <<'PY'
import json,sys
from pathlib import Path
result=json.loads(Path(sys.argv[1]).read_text())
if result.get('finish_reason') not in ('stop','tool_calls'):
    raise SystemExit('Replay did not finish normally')
print(json.dumps(result,sort_keys=True))
PY
