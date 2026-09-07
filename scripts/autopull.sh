#!/usr/bin/env bash
# autopull.sh — Automatically pull new Patreon chapters, process, and export.
#
# Deterministic pipeline with Claude headless for commentary detection.
# Designed to run from cron/launchd unattended.

set -euo pipefail

# launchd hands its jobs a 256-descriptor soft limit, which a long chapter can
# exhaust mid-generation: the backend then dies with EMFILE, and because the
# chapter already has normalized.txt the precheck can't see the half-finished
# work, so no later run picks it up. Raise the soft limit (the hard limit is
# unlimited) so a single chapter can't run the process out of descriptors.
ulimit -n 8192 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FICTION_ID="${FICTION_ID:-124774}"
API="http://localhost:8000"
LOG_FILE="$PROJECT_DIR/logs/autopull.log"
VENV="$PROJECT_DIR/venv311/bin/activate"
PYTHON="$PROJECT_DIR/venv311/bin/python"

LOCK_DIR="$PROJECT_DIR/.autopull.lock"
STATUS_FILE="$PROJECT_DIR/logs/autopull.last_status"

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

write_status() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" > "$STATUS_FILE" 2>/dev/null || true; }

# Carry a dead run into the next tick's log. A run that exits non-zero says so
# once and is then buried by later ticks; one killed outright (reboot, OOM) never
# gets to say anything at all, and leaves the status file reading "running".
report_last_status() {
  [ -f "$STATUS_FILE" ] || return 0
  local last
  last=$(cat "$STATUS_FILE" 2>/dev/null || echo "")
  case "$last" in
    *exit=0) ;;
    *running*) log "WARNING: previous run was killed before it finished ($last)" ;;
    *) log "WARNING: previous run failed ($last)" ;;
  esac
}

# Post a macOS notification (best-effort; works from a user LaunchAgent).
notify() {
  local title=$1 msg=$2
  osascript -e "display notification \"${msg}\" with title \"${title}\"" 2>/dev/null || true
}

# Runs on every exit AFTER the lock is acquired: release the lock and, on a
# non-zero exit, surface the failure (the script otherwise dies silently under
# `set -e`, which is exactly what we're fixing).
cleanup() {
  local code=$?
  # rm -rf, not rmdir: the lock dir always holds a `pid` file, so rmdir would
  # fail on the non-empty dir and leak the lock — forcing every subsequent run
  # down the stale-reclaim path. Remove the dir and its contents outright.
  rm -rf "$LOCK_DIR" 2>/dev/null || true
  write_status "exit=$code"
  if [ "$code" -ne 0 ]; then
    log "ERROR: Autopull exited with code $code"
    notify "Audiobook autopull failed" "Exit $code — see logs/autopull.log"
    # Best-effort run.error event for pollers; never mask the original exit code.
    curl -sf -X POST "$API/api/events" \
      -H 'Content-Type: application/json' \
      -d "{\"type\": \"run.error\", \"fiction_id\": \"${FICTION_ID}\", \"book\": ${BOOK:-null}, \"severity\": \"error\", \"detail\": {\"exit_code\": $code}}" \
      >/dev/null 2>&1 || true
  fi
}

# Single-instance guard. A TTS generation can run ~1hr/chapter and exceed the
# launchd poll interval, so overlapping runs must be prevented. launchd already
# treats the job as a singleton, but this also covers manual `bash autopull.sh`
# invocations racing a scheduled run. mkdir is atomic; a dead holder's lock is
# reclaimed.
acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo $$ > "$LOCK_DIR/pid"
    trap cleanup EXIT
    return 0
  fi
  local holder
  holder=$(cat "$LOCK_DIR/pid" 2>/dev/null || echo "")
  if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
    log "Another autopull run is active (PID $holder); exiting without action"
    exit 0
  fi
  log "Reclaiming stale lock (holder PID ${holder:-unknown} not running)"
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR"
  echo $$ > "$LOCK_DIR/pid"
  trap cleanup EXIT
}

# Strip markdown code fences from Claude output. Claude sometimes wraps its
# JSON in ```json ... ``` fences, which apply_commentary.py then parses as
# "nothing to remove", leaking author commentary into the audiobook. Drop any
# line that is a fence.
strip_fences() { printf '%s' "$1" | sed -E '/^[[:space:]]*```/d'; }

# --- Step 1: Ensure backend is running ---
ensure_backend() {
  if curl -sf "$API/api/queue/status" > /dev/null 2>&1; then
    log "Backend already running"
    return 0
  fi

  log "Starting backend..."
  cd "$PROJECT_DIR/backend"
  source "$VENV"
  python main.py >> "$LOG_FILE" 2>&1 &
  BACKEND_PID=$!

  for i in $(seq 1 30); do
    sleep 1
    if curl -sf "$API/api/queue/status" > /dev/null 2>&1; then
      log "Backend started (PID $BACKEND_PID)"
      return 0
    fi
  done

  log "ERROR: Backend failed to start"
  exit 1
}

# --- Step 2: Determine latest book ON DISK ---
get_latest_book() {
  ls "$PROJECT_DIR/data/books/$FICTION_ID/" | grep book_ | sort -V | tail -1 | sed 's/book_//'
}

# --- Step 3: Discover books available AT THE SOURCE ---
# Prints the book numbers the upstream source currently offers (honoring the
# patreon_meta.json bridge). Empty on any failure (network/cookie), so the
# caller can fall back to the on-disk view instead of skipping the run.
get_source_books() {
  "$PYTHON" "$SCRIPT_DIR/source_books.py" "$FICTION_ID" 2>/dev/null | grep -E '^[0-9]+$' || true
}

# Books worth checking this run: every source book at or beyond the highest book
# already on disk. This re-checks the latest on-disk book for new chapters AND
# picks up a freshly started book (e.g. Book 8) that has no directory yet, while
# leaving older, completed books untouched. Falls back to the on-disk book alone
# when source discovery yields nothing.
books_to_process() {
  local on_disk=${1:-0}
  local source_books
  source_books=$(get_source_books)
  if [ -z "$source_books" ]; then
    echo "$on_disk"
    return 0
  fi
  echo "$source_books" | awk -v floor="${on_disk:-0}" '$1 >= floor'
}

# --- Precheck: books with pending work, WITHOUT booting the backend ---
# Prints book numbers that either have a newly published source chapter or a
# half-processed chapter still on disk. Runs the scraper only — no FastAPI, no
# torch, no TTS model — so idle 15-minute polls stay cheap. Exit 0 means it ran
# cleanly (empty stdout == nothing to do); a non-zero exit means the source fetch
# failed and the caller should fall back rather than skip real work.
run_precheck() {
  "$PYTHON" "$SCRIPT_DIR/pending_work.py" "$FICTION_ID" 2>/dev/null
}

# --- Step 4: Download new chapters ---
download_chapters() {
  local book=$1
  log "Downloading chapters for book $book..."

  curl -sf -X POST "$API/api/scraper/download" \
    -H 'Content-Type: application/json' \
    -d "{\"fiction_id\": \"$FICTION_ID\", \"book_number\": $book}" > /dev/null

  # Poll until complete
  for i in $(seq 1 120); do
    sleep 2
    local status
    status=$(curl -sf "$API/api/downloads/$FICTION_ID/$book" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
    if [ "$status" = "completed" ]; then
      local total
      total=$(curl -sf "$API/api/downloads/$FICTION_ID/$book" | python3 -c "import sys,json; print(json.load(sys.stdin)['progress_chapters'])")
      log "Download complete: $total chapters on disk"
      echo "$total"
      return 0
    elif [ "$status" = "failed" ]; then
      log "ERROR: Download failed"
      exit 1
    fi
  done

  log "ERROR: Download timed out"
  exit 1
}

# --- Step 5: Find new chapters ---
find_new_chapters() {
  local book=$1
  local new_chapters=()
  for ch_dir in "$PROJECT_DIR/data/books/$FICTION_ID/book_$book/chapters"/chapter_*/; do
    [ -d "$ch_dir" ] || continue
    local ch
    ch=$(basename "$ch_dir" | sed 's/chapter_//')
    if [ -f "$ch_dir/raw.txt" ] && [ ! -f "$ch_dir/normalized.txt" ]; then
      new_chapters+=("$ch")
    fi
  done
  [ ${#new_chapters[@]} -eq 0 ] && return 0
  # Emit in numeric order. The glob above expands lexicographically
  # (chapter_10 before chapter_2/chapter_9), which would otherwise process
  # chapter 10 before chapter 9. echo is unquoted so newlines collapse to spaces.
  local sorted
  sorted=$(printf '%s\n' "${new_chapters[@]}" | sort -n)
  echo $sorted
}

# --- Step 5a: Find chapters a previous run left mid-pipeline ---
# Emits "chapter:stage:wavs:texts" per interrupted chapter (see pending_work.py).
# These are invisible to find_new_chapters, which only looks for a chapter with
# raw.txt and no normalized.txt.
find_interrupted_chapters() {
  local book=$1
  "$PYTHON" "$SCRIPT_DIR/pending_work.py" "$FICTION_ID" --interrupted "$book" 2>/dev/null || true
}

# Echoes "<chunk wavs> <chunk texts>" for a chapter.
chunk_progress() {
  local chunks_dir="$PROJECT_DIR/data/books/$FICTION_ID/book_$1/chapters/chapter_$2/chunks"
  local texts wavs
  texts=$(ls "$chunks_dir"/*.txt 2>/dev/null | wc -l | tr -d ' ')
  wavs=$(ls "$chunks_dir"/*.wav 2>/dev/null | wc -l | tr -d ' ')
  echo "$wavs $texts"
}

chunks_missing() {
  local wavs texts
  read -r wavs texts <<< "$(chunk_progress "$1" "$2")"
  [ "$texts" -gt 0 ] && [ "$wavs" -lt "$texts" ]
}

# Export and publish a chapter, but only once every chunk has audio.
#
# Generation reporting "complete" with chunks still unrendered means those chunks
# carry a .error file, which makes them FAILED rather than PENDING, so
# /api/generate will not re-queue them. Concatenation drops missing chunks
# silently and export writes completed_at, so shipping here would publish a
# chapter with silent holes AND hide it from the recovery path forever. Blocking
# instead leaves it interrupted, so every later tick re-reports it.
publish_chapter() {
  local book=$1 ch=$2
  if chunks_missing "$book" "$ch"; then
    local wavs texts
    read -r wavs texts <<< "$(chunk_progress "$book" "$ch")"
    log "ERROR: book $book chapter $ch still missing chunk audio after generation ($wavs/$texts); not exporting"
    notify "Audiobook chapter blocked" "Book $book chapter $ch stuck at $wavs/$texts chunks — see logs/autopull.log"
    return 1
  fi
  export_chapter "$book" "$ch"
  publish_feed
}

# Re-enter the pipeline for one interrupted chapter at the stage it died at.
# Generation resumes by construction: /api/generate queues only chunks with no
# wav yet, so the finished ones are never re-synthesized.
resume_chapter() {
  local book=$1 entry=$2
  local ch stage wavs texts
  IFS=: read -r ch stage wavs texts <<< "$entry"
  log "WARNING: book $book chapter $ch interrupted at $wavs/$texts chunks; resuming at stage '$stage'"

  case "$stage" in
    chunk)
      normalize_and_chunk "$book" "$ch"
      detect_commentary "$book" "$ch"
      generate_audio "$book" "$ch"
      ;;
    generate)
      generate_audio "$book" "$ch"
      ;;
  esac

  publish_chapter "$book" "$ch" || return 0
  log "--- Book $book chapter $ch recovered ---"
  SUMMARY+="Book $book: recovered chapter $ch"$'\n'
}

resume_interrupted() {
  local book=$1
  local interrupted entry
  interrupted=$(find_interrupted_chapters "$book")
  [ -z "$interrupted" ] && return 0
  for entry in $interrupted; do
    resume_chapter "$book" "$entry"
  done
}

# --- Step 5b: Pin spoken renderings for any table we can't convert ---
# Runs BEFORE normalize, which refuses to pass an unrendered table to TTS. On
# failure we deliberately continue: the guardrail then stops the chapter with a
# clear error rather than this step guessing at narration.
render_tables() {
  local book=$1
  shift
  for ch in "$@"; do
    if "$PYTHON" "$SCRIPT_DIR/render_spec_blocks.py" "$FICTION_ID" "$book" "$ch" \
        >> "$LOG_FILE" 2>&1; then
      log "Table renderings up to date for chapter $ch"
    else
      log "WARNING: table rendering failed for chapter $ch (normalize will catch it)"
    fi
  done
}

# --- Step 6: Normalize and chunk (NEW CHAPTERS ONLY) ---
# IMPORTANT: Operating on the full book is destructive — re-chunking deletes
# existing chunk wavs for previously-processed chapters. Always pass the
# specific chapter_numbers we want to (re)process.
normalize_and_chunk() {
  local book=$1
  shift
  local chapter_numbers
  chapter_numbers=$(printf '%s,' "$@" | sed 's/,$//')
  local payload="{\"fiction_id\": \"$FICTION_ID\", \"book_number\": $book, \"chapter_numbers\": [$chapter_numbers]}"

  log "Normalizing chapters: $chapter_numbers"
  curl -sf -X POST "$API/api/normalize" \
    -H 'Content-Type: application/json' \
    -d "$payload" > /dev/null

  log "Chunking chapters: $chapter_numbers"
  curl -sf -X POST "$API/api/chunk" \
    -H 'Content-Type: application/json' \
    -d "$payload" > /dev/null
}

# --- Step 7: Commentary detection via Claude headless ---
detect_commentary() {
  local book=$1
  local chapter=$2
  local chapter_dir="$PROJECT_DIR/data/books/$FICTION_ID/book_$book/chapters/chapter_$chapter"
  local chunks_dir="$chapter_dir/chunks"

  # A chapter that has already been ruled on needs no second opinion: the
  # removals were applied to normalized.txt and are reapplied on every
  # re-normalize, so the chunks we're looking at are clean by construction.
  if [ -f "$chapter_dir/commentary.json" ]; then
    log "Commentary decisions on disk; skipping detection for chapter $chapter"
    return 0
  fi

  local total
  total=$(ls "$chunks_dir"/*.txt 2>/dev/null | wc -l | tr -d ' ')

  if [ "$total" -eq 0 ]; then
    log "WARNING: No chunks found for chapter $chapter"
    return 0
  fi

  log "Checking chapter $chapter for commentary ($total chunks)..."

  # Gather first 5 chunks (preamble check)
  local first_content=""
  for f in $(ls "$chunks_dir"/*.txt | head -5); do
    first_content+="=== $(basename "$f") ===
$(cat "$f")

"
  done

  # Gather last 10 chunks (commentary check) — wider window to ensure we capture
  # the "…" separator that often appears 5+ chunks before the very end.
  local last_content=""
  for f in $(ls "$chunks_dir"/*.txt | tail -10); do
    last_content+="=== $(basename "$f") ===
$(cat "$f")

"
  done

  # Claude call 1: check start of chapter for preamble
  # Be conservative — only flag content that is OBVIOUSLY author commentary
  # (e.g., "Thanks for your support!"), NOT chapter numbers, dates, or scene-setting.
  local preamble_result
  preamble_result=$(claude -p "$(cat <<PROMPT
You are checking the START of an audiobook chapter for author preamble that leaked in from the previous chapter.

Here are the first 5 chunks of Book $book Chapter $chapter:

$first_content

ONLY flag content as preamble if it is OBVIOUSLY author commentary (sign-offs like "Thanks for your support!", scheduling notes, Discord links). Be CONSERVATIVE — chapter titles, dates, scene-setting, and narrative descriptions are STORY CONTENT.

If any chunks are pure author preamble (not story content), output ONLY a JSON array of chunk filenames to delete, e.g. ["1.txt", "2.txt"].
If the first chunk has obvious preamble before the story (e.g., "Thanks for your support!\n\n…\n\n[chapter title]"), output: {"strip_start": "FILENAME", "remove_before": "EXACT TEXT WHERE STORY STARTS"}
If everything is story content (THIS IS THE COMMON CASE), output: []

Output ONLY the JSON, nothing else.
PROMPT
)" --output-format text < /dev/null 2>/dev/null || echo "[]")

  # Claude call 2: check end of chapter for commentary
  # Look for the "…" separator — everything after it is typically commentary.
  local commentary_result
  commentary_result=$(claude -p "$(cat <<PROMPT
You are checking the END of an audiobook chapter for author commentary that should be removed before TTS.

Common patterns:
- "Thanks for your support!" sign-offs
- Scheduling notes ("no chapter Friday", "Probably Tuesday")
- Discord links, reference links, "Shoutout to X"
- Word count notes ("Book N was X words")
- Discussion of feedback, future plans, appendices

Author commentary almost always appears AFTER a "…" ellipsis separator. Once you see "…" on its own line, EVERYTHING after it is commentary, often spanning MULTIPLE chunks.

Here are the last 10 chunks of Book $book Chapter $chapter:

$last_content

Output a JSON object:
{
  "delete_chunks": ["317.txt", "318.txt", "319.txt"],
  "strip_trailing": {"file": "316.txt", "remove_from": "…"}
}

- "delete_chunks": ALL filenames of commentary chunks (not just the first one)
- "strip_trailing": the LAST story chunk that has commentary appended, with the exact text to remove from (typically "…")
- Omit either key if not applicable

If everything is story content, output: {}

Output ONLY the JSON, nothing else.
PROMPT
)" --output-format text < /dev/null 2>/dev/null || echo "{}")

  # Strip code fences before the JSON parsers see the output
  preamble_result=$(strip_fences "$preamble_result")
  commentary_result=$(strip_fences "$commentary_result")

  log "Preamble check: $preamble_result"
  log "Commentary check: $commentary_result"

  # Apply commentary removals
  apply_commentary "$book" "$chapter" "$chunks_dir" "$preamble_result" "$commentary_result"
}

# --- Step 8: Apply commentary detection results ---
# Applies the removals to the chunk files AND to normalized.txt, then records
# them in commentary.json so a later re-chunk or re-normalize can't bring the
# commentary back (chunk filenames shift, so the record is by text).
apply_commentary() {
  local book=$1 chapter=$2 chunks_dir=$3 preamble=$4 commentary=$5
  local chapter_dir
  chapter_dir=$(dirname "$chunks_dir")

  "$PYTHON" "$SCRIPT_DIR/apply_commentary.py" "$chapter_dir" \
    --preamble "$preamble" --commentary "$commentary" 2>&1 |
    while IFS= read -r line; do log "  $line"; done
}

# --- Step 9: Generate audio ---
generate_audio() {
  local book=$1 chapter=$2
  local result
  result=$(curl -sf -X POST "$API/api/generate" \
    -H 'Content-Type: application/json' \
    -d "{\"fiction_id\": \"$FICTION_ID\", \"book_number\": $book, \"chapter_numbers\": [$chapter]}")

  local count
  count=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['count'])")
  log "Queued $count chunks for generation"

  # Poll until complete
  while true; do
    sleep 15
    local pending running
    pending=$(curl -sf "$API/api/queue/status" | python3 -c "import sys,json; print(json.load(sys.stdin)['pending'])")
    running=$(curl -sf "$API/api/queue/status" | python3 -c "import sys,json; print(json.load(sys.stdin)['running'])")
    if [ "$pending" = "0" ] && [ "$running" = "0" ]; then
      log "Audio generation complete"
      return 0
    fi
  done
}

# --- Step 10: Export ---
export_chapter() {
  local book=$1 chapter=$2
  local result
  result=$(curl -sf -X POST "$API/api/export" \
    -H 'Content-Type: application/json' \
    -d "{\"fiction_id\": \"$FICTION_ID\", \"book_number\": $book, \"chapter_number\": $chapter}")

  local path
  path=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['path'])")
  log "Exported: $path"
}

# --- Step 11: Publish to podcast feed ---
# Rebuild the RSS feed(s) and push the new mp3 + feed to R2 so the phone's
# podcast app auto-downloads it. Never fails the run: if delivery isn't
# configured it just rebuilds the feed locally; any upload error is logged.
publish_feed() {
  if "$PYTHON" "$SCRIPT_DIR/publish_feed.py" >> "$LOG_FILE" 2>&1; then
    log "Feed published"
  else
    log "WARNING: feed publish failed (non-fatal)"
  fi
}

# --- Process one book end-to-end: download, then process each new chapter ---
# Appends a one-line summary to SUMMARY for any book that had new chapters.
process_book() {
  local book=$1
  download_chapters "$book" > /dev/null

  # Finish what a killed run started before taking on anything new: recovered
  # chapters come earlier in reading order, so the feed stays in sequence.
  resume_interrupted "$book"

  local new_chapters
  new_chapters=$(find_new_chapters "$book")

  if [ -z "$new_chapters" ]; then
    log "Book $book: no new chapters"
    return 0
  fi

  log "Book $book new chapters: $new_chapters"
  render_tables "$book" $new_chapters
  normalize_and_chunk "$book" $new_chapters

  local done_chapters=""
  for ch in $new_chapters; do
    log "--- Processing book $book chapter $ch ---"
    detect_commentary "$book" "$ch"
    generate_audio "$book" "$ch"
    publish_chapter "$book" "$ch" || continue
    done_chapters+=" $ch"
    log "--- Book $book chapter $ch complete ---"
  done

  if [ -n "$done_chapters" ]; then
    SUMMARY+="Book $book:$done_chapters"$'\n'
  fi
}

# ============================================================
# Main
# ============================================================

# Wrapped in a function, and run only when executed rather than sourced, so the
# recovery helpers above can be sourced and exercised by tests.
main() {
  acquire_lock

  log "=== Autopull started ==="
  report_last_status
  write_status "running pid=$$"

  ON_DISK_BOOK=$(get_latest_book)

  # Cheap precheck BEFORE any backend/TTS startup: is there a new source chapter or
  # a half-processed chapter on disk? Only boot the backend (and eventually the TTS
  # model, which loads lazily on first generation) when there is confirmed work.
  if BOOKS=$(run_precheck); then
    if [ -z "$BOOKS" ]; then
      log "Precheck: no new chapters — skipping backend startup"
      log "=== Autopull complete (no changes) ==="
      exit 0
    fi
    log "Precheck: books with pending work: $(echo $BOOKS | tr '\n' ' ')"
  else
    # Source fetch failed (network/cookie/parse). Don't skip on a transient blip —
    # fall back to full discovery, which itself degrades to the on-disk book.
    log "Precheck failed; falling back to full discovery"
    BOOKS=$(books_to_process "$ON_DISK_BOOK")
  fi

  ensure_backend

  # BOOK stays in scope for the cleanup trap's run.error event. SUMMARY collects
  # per-book results across the loop for the final notification.
  BOOK=$ON_DISK_BOOK
  SUMMARY=""
  for BOOK in $BOOKS; do
    process_book "$BOOK"
  done

  if [ -n "$SUMMARY" ]; then
    log "=== Autopull complete ==="
    notify "Audiobook autopull complete" "$SUMMARY"
  else
    log "=== Autopull complete (no changes) ==="
  fi
}

# Only self-execute; sourcing (tests) loads the helpers without running a pull.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
