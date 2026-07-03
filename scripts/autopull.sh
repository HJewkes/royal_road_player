#!/usr/bin/env bash
# autopull.sh — Automatically pull new Patreon chapters, process, and export.
#
# Deterministic pipeline with Claude headless for commentary detection.
# Designed to run from cron/launchd unattended.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FICTION_ID="${FICTION_ID:-124774}"
API="http://localhost:8000"
LOG_FILE="$PROJECT_DIR/logs/autopull.log"
VENV="$PROJECT_DIR/venv311/bin/activate"
PYTHON="$PROJECT_DIR/venv311/bin/python"

LOCK_DIR="$PROJECT_DIR/.autopull.lock"

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

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
# JSON in ```json ... ``` fences, which breaks the json.load() parsers in
# apply_commentary (they fail silently via `except: pass`, leaking author
# commentary into the audiobook). Drop any line that is a fence.
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
  local chunks_dir="$PROJECT_DIR/data/books/$FICTION_ID/book_$book/chapters/chapter_$chapter/chunks"
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
apply_commentary() {
  local book=$1 chapter=$2 chunks_dir=$3 preamble=$4 commentary=$5

  # Process commentary (end of chapter) — this is the common case
  local delete_chunks
  delete_chunks=$(echo "$commentary" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for f in d.get('delete_chunks', []):
        print(f)
except:
    pass
" 2>/dev/null)

  while IFS= read -r chunk_file; do
    [ -z "$chunk_file" ] && continue
    local chunk_path="$chunks_dir/$chunk_file"
    if [ -f "$chunk_path" ]; then
      rm -f "$chunk_path" "${chunk_path%.txt}.wav" "${chunk_path%.txt}.error"
      log "  Deleted commentary chunk: $chunk_file"
    fi
  done <<< "$delete_chunks"

  # Process strip_trailing
  local strip_file strip_text
  strip_file=$(echo "$commentary" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    s = d.get('strip_trailing', {})
    print(s.get('file', ''))
except:
    pass
" 2>/dev/null)

  strip_text=$(echo "$commentary" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    s = d.get('strip_trailing', {})
    print(s.get('remove_from', ''))
except:
    pass
" 2>/dev/null)

  if [ -n "$strip_file" ] && [ -n "$strip_text" ]; then
    local target="$chunks_dir/$strip_file"
    if [ -f "$target" ]; then
      python3 -c "
import sys
text = open('$target').read()
marker = '''$strip_text'''
idx = text.find(marker)
if idx > 0:
    cleaned = text[:idx].rstrip() + '\n'
    open('$target', 'w').write(cleaned)
    print(f'Stripped trailing from $strip_file at position {idx}')
else:
    print(f'WARNING: Could not find marker in $strip_file')
" 2>/dev/null | while read -r line; do log "  $line"; done
      rm -f "${target%.txt}.wav"
    fi
  fi

  # Process preamble (start of chapter) — rare but handle it
  local preamble_deletes
  preamble_deletes=$(echo "$preamble" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if isinstance(d, list):
        for f in d:
            print(f)
except:
    pass
" 2>/dev/null)

  while IFS= read -r chunk_file; do
    [ -z "$chunk_file" ] && continue
    local chunk_path="$chunks_dir/$chunk_file"
    if [ -f "$chunk_path" ]; then
      rm -f "$chunk_path" "${chunk_path%.txt}.wav" "${chunk_path%.txt}.error"
      log "  Deleted preamble chunk: $chunk_file"
    fi
  done <<< "$preamble_deletes"

  # Process strip_start (preamble mixed into first story chunk)
  local strip_start_file strip_start_text
  strip_start_file=$(echo "$preamble" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if isinstance(d, dict):
        print(d.get('strip_start', ''))
except:
    pass
" 2>/dev/null)

  strip_start_text=$(echo "$preamble" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if isinstance(d, dict):
        print(d.get('remove_before', ''))
except:
    pass
" 2>/dev/null)

  if [ -n "$strip_start_file" ] && [ -n "$strip_start_text" ]; then
    local target="$chunks_dir/$strip_start_file"
    if [ -f "$target" ]; then
      python3 -c "
text = open('$target').read()
marker = '''$strip_start_text'''
idx = text.find(marker)
if idx > 0:
    cleaned = text[idx:]
    open('$target', 'w').write(cleaned)
    print(f'Stripped preamble from $strip_start_file up to position {idx}')
else:
    print(f'WARNING: Could not find marker in $strip_start_file')
" 2>/dev/null | while read -r line; do log "  $line"; done
      rm -f "${target%.txt}.wav"
    fi
  fi
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

# --- Process one book end-to-end: download, then process each new chapter ---
# Appends a one-line summary to SUMMARY for any book that had new chapters.
process_book() {
  local book=$1
  download_chapters "$book" > /dev/null
  local new_chapters
  new_chapters=$(find_new_chapters "$book")

  if [ -z "$new_chapters" ]; then
    log "Book $book: no new chapters"
    return 0
  fi

  log "Book $book new chapters: $new_chapters"
  normalize_and_chunk "$book" $new_chapters

  for ch in $new_chapters; do
    log "--- Processing book $book chapter $ch ---"
    detect_commentary "$book" "$ch"
    generate_audio "$book" "$ch"
    export_chapter "$book" "$ch"
    log "--- Book $book chapter $ch complete ---"
  done

  SUMMARY+="Book $book: $new_chapters"$'\n'
}

# ============================================================
# Main
# ============================================================

acquire_lock

log "=== Autopull started ==="

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
