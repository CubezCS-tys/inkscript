#!/bin/bash
# Copy everything the repo does not hold (experiment outputs, the databases, the caches, the agent's notes) from
# this laptop to the server, so the server's checkout looks like this one. Run it on the LAPTOP, from the repo:
#
#     ops/pack_v2.sh --dry-run prod:/home/appuser     # what would go, folder by folder, and the total; copies nothing
#     ops/pack_v2.sh prod:/home/appuser               # the copy itself; resumable: run it again until it says done
#
# The argument is the server's HOME (user@host:/path, an ssh alias:/path, or a local directory for a test).
# Layout over there: <home>/inkscript/experiments/*/out, <home>/data/{marc,platform,platform_v2},
# <home>/.cache/inkscript, <home>/.claude/projects/<that checkout's folder name>/memory.
# The server must already have the clone at <home>/inkscript (docs/moving-to-a-server.md, step 1).
#
# rsync -a -H --partial -z: -H keeps hard links (experiments 41 and 43 share 7,324 scan pictures as hard links, and
# 43's runs share more among themselves: 10 GB counted once, not twice); 41 and 43 therefore go in one rsync. Symlinks are copied as symlinks (the views folders are symlinks into
# experiments/43_rehearsal/out; absolute ones point at /home/yassine/... and work once the path fix of
# docs/moving-to-a-server.md is done). A re-run skips every file already there with the same size and time.
# Never sent: .env, ~/.aws, ~/.ssh, metadata_final.xml (and its .gz), the experiment venvs (not portable;
# rebuild them), 39's gpu/result.tgz (an archive of what is unpacked beside it).
set -u
cd "$(dirname "$(readlink -f "$0")")/.."
REPO=$PWD

DRY=0; ONLY=""
while [ $# -gt 1 ]; do
  case "$1" in
    --dry-run|-n) DRY=1; shift ;;
    --only) ONLY=$2; shift 2 ;;     # optional: only folders whose name matches this regex, e.g. --only 'platform|43_'
    *) break ;;
  esac
done
DEST=${1:-}
if [ -z "$DEST" ] || [ $# -ne 1 ]; then
  echo "usage: ops/pack_v2.sh [--dry-run] [--only REGEX] HOST:/server/home   (e.g. prod:/home/appuser)"; exit 2
fi
DEST=${DEST%/}
case "$DEST" in
  *:*) RHOME=${DEST#*:} ;;
  *)   RHOME=$DEST ;;
esac
case "$RHOME" in /*) ;; *) echo "give the server home as an absolute path (prod:/home/appuser)"; exit 2 ;; esac
command -v rsync >/dev/null || { echo "rsync is not installed here"; exit 1; }

# The folder name Claude Code gives a checkout's notes: its path with / turned into -.
MEMDIR_LOCAL="$HOME/.claude/projects/$(echo "$REPO" | sed 's/[^a-zA-Z0-9]/-/g')/memory"
MEMDIR_REMOTE=".claude/projects/$(echo "$RHOME/inkscript" | sed 's/[^a-zA-Z0-9]/-/g')/memory"

NEVER=(--exclude=.env --exclude='.env.*' --exclude=.aws/ --exclude=.ssh/ --exclude='metadata_final.xml*'
       --exclude=__pycache__/)

# ITEMS: "local source dir|path under the server home|extra rsync options". Most needed first, so the server
# agent can start on the rehearsal and the platform before the older experiments arrive.
ITEMS=(
  "$HOME/.cache/inkscript|.cache/inkscript|"
  "$HOME/data/platform|data/platform|"
  "$HOME/data/platform_v2|data/platform_v2|"
  "$REPO/experiments|inkscript/experiments|--include=/43_rehearsal/ --include=/43_rehearsal/out/*** --include=/41_azure_structure/ --include=/41_azure_structure/out/*** --exclude=*"
  "$REPO/experiments/47_platform_v2/out|inkscript/experiments/47_platform_v2/out|"
  "$REPO/experiments/44_bucket_map/out|inkscript/experiments/44_bucket_map/out|"
  "$REPO/experiments/40_gemini4_vlm/out|inkscript/experiments/40_gemini4_vlm/out|--exclude=/venv/"
  "$REPO/experiments/42_stroke_recovery/out|inkscript/experiments/42_stroke_recovery/out|"
  "$MEMDIR_LOCAL|$MEMDIR_REMOTE|"
  "$HOME/data/marc|data/marc|--exclude=/slice/"
)
# then every other experiment's out/, newest first (the ones above are skipped here)
OUTS=$(ls -d "$REPO"/experiments/*/out 2>/dev/null | sort -r)
set -f   # from here on no shell globbing: the rsync patterns above must reach rsync as written
for d in $OUTS; do
  name=$(basename "$(dirname "$d")")
  case "$name" in 43_rehearsal|41_azure_structure|47_platform_v2|44_bucket_map|40_gemini4_vlm|42_stroke_recovery) continue ;; esac
  extra=""
  case "$name" in
    39_ink_geometry) extra="--exclude=/venv/ --exclude=/gpu/result.tgz" ;;
    33_kraken)       extra="--exclude=/env/" ;;
    16_feel)         extra="--exclude=/torchenv/" ;;
  esac
  ITEMS+=("$d|inkscript/experiments/$name/out|$extra")
done

human() { numfmt --to=si --suffix=B --format='%.1f' "${1:-0}" 2>/dev/null || echo "${1:-0} B"; }
# what rsync would send for one item: prints "files bytes total_bytes"
measure() {
  local src=$1 dst=$2; shift 2
  rsync -a -H -z --dry-run --stats "${NEVER[@]}" "$@" --mkpath "$src/" "$dst/" 2>/dev/null | awk -F': ' '
    /^Number of regular files transferred/ {gsub(/,/,"",$2); f=$2}
    /^Total file size/                     {gsub(/,/,"",$2); split($2,a," "); t=a[1]}
    /^Total transferred file size/         {gsub(/,/,"",$2); split($2,a," "); b=a[1]}
    END {print (f==""?0:f), (b==""?0:b), (t==""?0:t)}'
}

N=${#ITEMS[@]}
echo "== $( [ $DRY = 1 ] && echo 'DRY RUN, nothing is copied' || echo 'COPY' ) -> $DEST  ($N folders)"
echo "   never sent: .env, ~/.aws, ~/.ssh, metadata_final.xml*, experiment venvs, 39's gpu/result.tgz, ~/data/marc/slice"
SUM_SEND=0; SUM_ALL=0; i=0; FAILED=()
for it in "${ITEMS[@]}"; do
  i=$((i+1))
  src=${it%%|*}; rest=${it#*|}; rel=${rest%%|*}; extra=${rest#*|}
  label=${src#$REPO/}; label=${label/#$HOME/\~}
  [ "$src" = "$REPO/experiments" ] && label="experiments/{43_rehearsal,41_azure_structure}/out"
  if [ -n "$ONLY" ] && ! [[ "$label" =~ $ONLY ]]; then continue; fi
  if [ ! -d "$src" ]; then printf '[%2d/%d] %-48s not on this laptop, skipped\n' $i $N "$label"; continue; fi
  # shellcheck disable=SC2086
  read -r nf nb nt < <(measure "$src" "$DEST/$rel" $extra)
  SUM_SEND=$((SUM_SEND+nb)); SUM_ALL=$((SUM_ALL+nt))
  if [ "$nf" = 0 ]; then
    printf '[%2d/%d] %-56s already there, skipped\n' $i $N "$label"; continue
  fi
  printf '[%2d/%d] %-56s to send: %9s in %s files\n' $i $N "$label" "$(human $nb)" "$nf"
  [ $DRY = 1 ] && continue
  # shellcheck disable=SC2086
  if ! rsync -a -H --partial -z --mkpath --info=progress2,stats0 "${NEVER[@]}" $extra "$src/" "$DEST/$rel/"; then
    echo "        !! rsync stopped on $label (network?). Run the same command again: it resumes."
    FAILED+=("$label")
  fi
done
echo "== still to send at the start of this run: $(human $SUM_SEND)  (hard-linked files counted once)"
if [ $DRY = 1 ]; then
  echo "   at about 1 MB/s upload, $(human $SUM_SEND) takes about $(((SUM_SEND+1800000000)/3600000000)) h (rsync -z shrinks the text and the databases; pictures do not shrink)"
elif [ ${#FAILED[@]} -gt 0 ]; then
  echo "== NOT done: ${FAILED[*]}"; echo "   run: ops/pack_v2.sh $DEST"; exit 1
else
  echo "== done. Run it once more: every line should say 'already there'."
fi
