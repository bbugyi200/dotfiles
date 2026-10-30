#!/bin/bash

#################################################################################
# Regression tests for the research-file hook stable-recapture adapter.         #
# Offline only: stubs `bob` on PATH, never touches the live vault.              #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_bob_research_capture"
SASE_YML="${PWD}/home/dot_config/sase/sase.yml"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  REPORTS_DIR="${TEST_TMP}/reports"
  FIXTURES_DIR="${TEST_TMP}/fixtures"
  CALLS_FILE="${TEST_TMP}/bob-create-calls.jsonl"
  SHOW_LOG="${TEST_TMP}/bob-show-queries.log"
  mkdir -p "${FAKE_BIN}" "${REPORTS_DIR}" "${FIXTURES_DIR}"
  : >"${CALLS_FILE}"
  : >"${SHOW_LOG}"
  write_fake_bob
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function write_fake_bob() {
  cat >"${FAKE_BIN}/bob" <<'FAKEEOF'
#!/bin/bash
CALLS_FILE="${CALLS_FILE:?}"
SHOW_LOG="${SHOW_LOG:-/dev/null}"
FIXTURES_DIR="${BOB_SHOW_FIXTURES:-}"
if [[ "$1" == "ref" && "$2" == "show" ]]; then
  query="$3"
  printf '%s\n' "$query" >>"$SHOW_LOG"
  safe="$(printf '%s' "$query" | sed 's|/|__SLASH__|g')"
  fixture="${FIXTURES_DIR}/show__${safe}.json"
  code_file="${FIXTURES_DIR}/show__${safe}.exit"
  code="0"
  if [[ -f "$code_file" ]]; then code="$(cat "$code_file")"; fi
  if [[ -f "$fixture" ]]; then cat "$fixture"; exit "$code"; fi
  printf '{"ok": false, "schema_version": 1, "command": "ref show", "error": {"code": "unknown_reference", "message": "no reference note matches %s"}}\n' "$query"
  exit 1
elif [[ "$1" == "ref" && "$2" == "create" ]]; then
  shift 2
  python3 -c 'import json,os,sys; open(os.environ["CALLS_FILE"],"a").write(json.dumps(sys.argv[1:])+"\n")' "$@"
  exit "${BOB_CREATE_EXIT:-0}"
else
  echo "unexpected bob invocation: $*" >&2
  exit 2
fi
FAKEEOF
  chmod +x "${FAKE_BIN}/bob"
}

function write_report() {
  local rel="$1"
  local title="${2:-Test Report}"
  local full="${REPORTS_DIR}/${rel}"
  mkdir -p "$(dirname "$full")"
  printf '# %s\n\nBody.\n' "$title" >"$full"
  printf '%s' "$full"
}

function run_capture() {
  PATH="${FAKE_BIN}:/usr/bin:/bin" \
    BOB_SHOW_FIXTURES="${FIXTURES_DIR}" \
    CALLS_FILE="${CALLS_FILE}" \
    SHOW_LOG="${SHOW_LOG}" \
    SASE_FILE_HOOK_PROJECT="${HOOK_PROJECT-test-project}" \
    python3 "${SCRIPT}" "$@"
}

function create_call_count() {
  if [[ ! -s "${CALLS_FILE}" ]]; then printf '0'; return; fi
  wc -l <"${CALLS_FILE}" | tr -d '[:space:]'
}

function last_create_json() {
  tail -n 1 "${CALLS_FILE}"
}

function create_arg() {
  last_create_json | python3 -c 'import json,sys; argv=json.load(sys.stdin); print(argv[int(sys.argv[1])] if int(sys.argv[1]) < len(argv) else "MISSING")' "$1"
}

function create_has_flag() {
  last_create_json | python3 -c 'import json,sys; argv=json.load(sys.stdin); sys.exit(0 if sys.argv[1] in argv else 1)' "$1"
}

function write_show_row() {
  local query="$1"
  local path="$2"
  local status="$3"
  local sync="$4"
  local highlights_py="$5"
  local annotations="$6"
  local reading_py="$7"
  local later_py="$8"
  local safe
  safe="$(printf '%s' "$query" | sed 's|/|__SLASH__|g')"
  QUERY="$query" ROW_PATH="$path" ROW_STATUS="$status" ROW_SYNC="$sync" \
    ROW_HL="$highlights_py" ROW_ANN="$annotations" ROW_READING="$reading_py" \
    ROW_LATER="$later_py" OUT="$FIXTURES_DIR/show__${safe}.json" python3 <<'PY'
import json, os
def parse(v):
    if v == "__NONE__":
        return None
    try:
        return json.loads(v)
    except Exception:
        return v
path = os.environ["ROW_PATH"]
status = os.environ["ROW_STATUS"]
sync = os.environ["ROW_SYNC"]
hl = parse(os.environ["ROW_HL"])
ann = int(os.environ["ROW_ANN"])
reading = parse(os.environ["ROW_READING"])
later = parse(os.environ["ROW_LATER"])
row = {
    "path": path, "link": path, "title": "T", "marker_id": None,
    "origin": "ref", "ref_type": "chat", "era": "modern",
    "status": None if status == "__NONE__" else status,
    "status_sync": sync, "legacy_status": None,
    "reading_state": "queued", "reading_state_source": "frontmatter:ready",
    "blocked": False, "blocked_by": [], "parent": "sase",
    "task": None, "urls": [], "earlier": [], "reading": reading,
    "identity": {"keys": [], "arxiv": None, "doi": None},
    "author": None, "published": None, "captured": "2026-01-01",
    "added": None, "added_source": None, "added_at": None,
    "finished": None, "finished_source": None,
    "source_pdf": "lib/chat/x.pdf", "audio": None,
    "annotation_count": ann, "comment_count": 0,
    "snapshot": {"synced_at": "2026-01-01T00:00:00", "highlights_count": hl},
    "research_ref": None, "source_markdown": None,
    "superseded_by": None, "diagnostics": [], "later": later,
    "annotations": [], "excluded": {"marker_mirrors": 0, "preamble": 0, "removed": 0},
    "own_notes": "", "tasks": [], "also": [],
}
env = {
    "ok": True, "schema_version": 1, "command": "ref show",
    "generated_at": "2026-01-01T00:00:00",
    "coverage": {"ref_dir": "ref", "notes": 1, "skipped": 0, "intake": "ok", "scope": "s", "annotations": "a"},
    "library": {"total": 1},
    "refs": [row],
}
open(os.environ["OUT"], "w").write(json.dumps(env))
PY
}

function write_show_error() {
  local query="$1"
  local code="$2"
  local exit_code="${3:-1}"
  local safe
  safe="$(printf '%s' "$query" | sed 's|/|__SLASH__|g')"
  printf '{"ok": false, "schema_version": 1, "command": "ref show", "error": {"code": "%s", "message": "probe %s"}}' "$code" "$query" >"$FIXTURES_DIR/show__${safe}.json"
  printf '%s' "$exit_code" >"$FIXTURES_DIR/show__${safe}.exit"
}

function write_show_raw() {
  local query="$1"
  local body="$2"
  local exit_code="${3:-0}"
  local safe
  safe="$(printf '%s' "$query" | sed 's|/|__SLASH__|g')"
  printf '%s' "$body" >"$FIXTURES_DIR/show__${safe}.json"
  printf '%s' "$exit_code" >"$FIXTURES_DIR/show__${safe}.exit"
}

function test_hash_suffix_is_stripped_for_both_hashes() {
  local r1 r2
  r1="$(write_report "my_report-ad048d84997e.md")"
  r2="$(write_report "my_report-460733ec5bb6.md")"
  HOOK_PROJECT="proj" run_capture "$r1"
  assert_same "0" "$?"
  assert_same "1" "$(create_call_count)"
  local n1
  n1="$(last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); print(a[a.index("-N")+1])')"
  assert_same "my_report" "$n1"
  : >"$CALLS_FILE"
  HOOK_PROJECT="proj" run_capture "$r2"
  assert_same "0" "$?"
  local n2
  n2="$(last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); print(a[a.index("-N")+1])')"
  assert_same "my_report" "$n2"
}

function test_plain_and_nonmatching_suffixes_unchanged() {
  local r
  r="$(write_report "my_report.md")"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "my_report" "$(last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); print(a[a.index("-N")+1])')"
  : >"$CALLS_FILE"
  r="$(write_report "my_report-xyz.md")"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "my_report-xyz" "$(last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); print(a[a.index("-N")+1])')"
  : >"$CALLS_FILE"
  r="$(write_report "my_report-12345.md")"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "my_report-12345" "$(last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); print(a[a.index("-N")+1])')"
}

function test_spaces_and_gem_suffix_preserved() {
  local r
  r="$(write_report "my dir/agent_data_decks_and_cards__gem-4de479cbc0d1.md")"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  assert_same "agent_data_decks_and_cards__gem" "$(last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); print(a[a.index("-N")+1])')"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert a[0] == sys.argv[1], a' "$r"
  assert_same "0" "$?"
}

function test_invalid_inputs_make_no_create_call() {
  HOOK_PROJECT="proj" run_capture >/dev/null 2>&1
  assert_same "2" "$?"
  assert_same "0" "$(create_call_count)"
  local r1 r2
  r1="$(write_report "a-ad048d84997e.md")"
  r2="$(write_report "b-460733ec5bb6.md")"
  HOOK_PROJECT="proj" run_capture "$r1" "$r2" >/dev/null 2>&1
  assert_same "2" "$?"
  assert_same "0" "$(create_call_count)"
  HOOK_PROJECT="proj" run_capture "${REPORTS_DIR}/missing-ad048d84997e.md" >/dev/null 2>&1
  assert_same "2" "$?"
  assert_same "0" "$(create_call_count)"
  local bad
  bad="$(write_report "-ad048d84997e.md")"
  HOOK_PROJECT="proj" run_capture "$bad" >/dev/null 2>&1
  assert_same "2" "$?"
  assert_same "0" "$(create_call_count)"
}

function test_first_capture_uses_stable_name_source_and_project() {
  local r
  r="$(write_report "first-take-ad048d84997e.md")"
  HOOK_PROJECT="exact-proj-1" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  assert_same "1" "$(create_call_count)"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert a[0] == sys.argv[1], a' "$r"
  assert_same "0" "$?"
  create_has_flag "--include-id"
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert a[a.index("-P")+1] == "exact-proj-1", a'
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert a[a.index("-N")+1] == "first-take", a'
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert "-f" in a and "-f=overwrite" not in a and "--force=overwrite" not in a, a'
  assert_same "0" "$?"
}

function test_missing_project_makes_no_writes() {
  local r
  r="$(write_report "proj-missing-ad048d84997e.md")"
  HOOK_PROJECT="" run_capture "$r" >/dev/null 2>&1
  assert_same "2" "$?"
  assert_same "0" "$(create_call_count)"
  unset HOOK_PROJECT
  PATH="${FAKE_BIN}:/usr/bin:/bin" BOB_SHOW_FIXTURES="${FIXTURES_DIR}" CALLS_FILE="${CALLS_FILE}" SHOW_LOG="${SHOW_LOG}" SASE_FILE_HOOK_PROJECT="" python3 "${SCRIPT}" "$r" >/dev/null 2>&1
  assert_same "2" "$?"
  assert_same "0" "$(create_call_count)"
  HOOK_PROJECT="  "
  run_capture "$r" >/dev/null 2>&1
  assert_same "2" "$?"
  assert_same "0" "$(create_call_count)"
}

function test_ready_zero_unannotated_selects_overwrite() {
  local r
  r="$(write_report "ready-zero-ad048d84997e.md")"
  write_show_row "ready-zero" "ref/chat/ready-zero.md" "ready" "ok" "0" "0" "__NONE__" "[]"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert "-f=overwrite" in a, a'
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert a[a.index("-N")+1] == "ready-zero", a'
  assert_same "0" "$?"
}

function test_nonready_and_annotated_select_reread() {
  local statuses=("next" "wip" "read" "abandoned")
  local s r
  for s in "${statuses[@]}"; do
    : >"$CALLS_FILE"
    rm -f "$FIXTURES_DIR"/show__*.json
    r="$(write_report "lane-${s}-ad048d84997e.md")"
    write_show_row "lane-${s}" "ref/chat/lane-${s}.md" "$s" "ok" "0" "0" "__NONE__" "[]"
    HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
    assert_same "0" "$?"
    last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert "-f" in a and "-f=overwrite" not in a, a'
    assert_same "0" "$?"
  done
  : >"$CALLS_FILE"
  rm -f "$FIXTURES_DIR"/show__*.json
  r="$(write_report "positive-hl-ad048d84997e.md")"
  write_show_row "positive-hl" "ref/chat/positive-hl.md" "ready" "ok" "3" "0" "__NONE__" "[]"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert "-f=overwrite" not in a, a'
  assert_same "0" "$?"
  for hl in "null" "true" "false" '"0"'; do
    : >"$CALLS_FILE"
    rm -f "$FIXTURES_DIR"/show__*.json
    r="$(write_report "unknown-hl-ad048d84997e.md")"
    write_show_row "unknown-hl" "ref/chat/unknown-hl.md" "ready" "ok" "$hl" "0" "__NONE__" "[]"
    HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
    assert_same "0" "$?"
    last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert "-f=overwrite" not in a, a'
    assert_same "0" "$?"
  done
  : >"$CALLS_FILE"
  rm -f "$FIXTURES_DIR"/show__*.json
  r="$(write_report "annotated-ad048d84997e.md")"
  write_show_row "annotated" "ref/chat/annotated.md" "ready" "ok" "0" "2" "__NONE__" "[]"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert "-f=overwrite" not in a, a'
  assert_same "0" "$?"
  : >"$CALLS_FILE"
  rm -f "$FIXTURES_DIR"/show__*.json
  r="$(write_report "conflict-ad048d84997e.md")"
  write_show_row "conflict" "ref/chat/conflict.md" "conflict" "conflict" "0" "0" "__NONE__" "[]"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert "-f=overwrite" not in a, a'
  assert_same "0" "$?"
}

function test_family_v2_overwrite_and_reread() {
  local r
  r="$(write_report "fam-root-ad048d84997e.md" "Fam")"
  write_show_row "fam-root" "ref/chat/fam-root.md" "read" "ok" "5" "1" "1" '["ref/chat/fam-root__v2.md"]'
  write_show_row "ref/chat/fam-root__v2.md" "ref/chat/fam-root__v2.md" "ready" "ok" "0" "0" "2" "[]"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert "-f=overwrite" in a and a[a.index("-N")+1] == "fam-root__v2", a'
  assert_same "0" "$?"
  rm -f "$FIXTURES_DIR"/show__*.json
  : >"$CALLS_FILE"
  : >"$SHOW_LOG"
  r="$(write_report "fam2-root-460733ec5bb6.md" "Fam2")"
  write_show_row "fam2-root" "ref/chat/fam2-root.md" "wip" "ok" "0" "0" "1" '["ref/chat/fam2-root__v2.md"]'
  write_show_row "ref/chat/fam2-root__v2.md" "ref/chat/fam2-root__v2.md" "read" "ok" "4" "0" "2" "[]"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert "-f" in a and "-f=overwrite" not in a, a'
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert "__v3" not in a[a.index("-N")+1], a'
  assert_same "0" "$?"
}

function test_version_looking_name_without_lineage_stays_standalone() {
  local r
  r="$(write_report "plain__v2.md" "Plain")"
  write_show_row "plain__v2" "ref/chat/plain__v2.md" "ready" "ok" "0" "0" "__NONE__" "[]"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert a[a.index("-N")+1] == "plain__v2", a'
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert not any("__v3" in x for x in a), a'
  assert_same "0" "$?"
}

function test_lookup_failures_make_no_create_call() {
  local r
  r="$(write_report "ambig-ad048d84997e.md")"
  write_show_error "ambig" "ambiguous_reference"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "1" "$?"
  assert_same "0" "$(create_call_count)"
  rm -f "$FIXTURES_DIR"/show__*.json "$FIXTURES_DIR"/show__*.exit
  write_show_error "gone" "missing_ref_dir"
  r="$(write_report "gone-ad048d84997e.md")"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "1" "$?"
  assert_same "0" "$(create_call_count)"
  rm -f "$FIXTURES_DIR"/show__*.json "$FIXTURES_DIR"/show__*.exit
  write_show_raw "badjson" "not json at all" "0"
  r="$(write_report "badjson-ad048d84997e.md")"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "1" "$?"
  assert_same "0" "$(create_call_count)"
  rm -f "$FIXTURES_DIR"/show__*.json "$FIXTURES_DIR"/show__*.exit
  printf '{"ok": true, "schema_version": 999, "command": "ref show", "refs": []}' >"$FIXTURES_DIR/show__schemabad.json"
  r="$(write_report "schemabad-ad048d84997e.md")"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "1" "$?"
  assert_same "0" "$(create_call_count)"
  rm -f "$FIXTURES_DIR"/show__*.json "$FIXTURES_DIR"/show__*.exit
  write_show_row "vanish" "ref/chat/vanish.md" "ready" "ok" "0" "0" "1" '["ref/chat/vanish__v2.md"]'
  r="$(write_report "vanish-ad048d84997e.md")"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "1" "$?"
  assert_same "0" "$(create_call_count)"
}

function test_create_failure_keeps_exit_and_no_fallback() {
  local r
  r="$(write_report "failmode-ad048d84997e.md")"
  BOB_CREATE_EXIT="3" HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "3" "$?"
  assert_same "1" "$(create_call_count)"
  unset BOB_CREATE_EXIT
}

function test_metachars_stay_single_literal_arguments() {
  local dir="we;ird \$(echo hi) \`id\`"
  local r
  r="$(write_report "${dir}/meta-ad048d84997e.md")"
  HOOK_PROJECT='proj; rm -rf $HOME $(id)' run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert a[0] == sys.argv[1], repr(a)' "$r"
  assert_same "0" "$?"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert a[a.index("-P")+1] == "proj; rm -rf $HOME $(id)", repr(a)'
  assert_same "0" "$?"
}

function test_canonical_month_dir_reports_are_captured() {
  local r
  r="$(write_report "202610/topic/topic.md")"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  assert_same "1" "$(create_call_count)"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert a[a.index("-N")+1] == "topic", a'
  assert_same "0" "$?"
  : >"$CALLS_FILE"
  r="$(write_report "202610/solo_report.md")"
  HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>&1
  assert_same "0" "$?"
  assert_same "1" "$(create_call_count)"
  last_create_json | python3 -c 'import json,sys; a=json.load(sys.stdin); assert a[a.index("-N")+1] == "solo_report", a'
  assert_same "0" "$?"
}

function test_non_canonical_month_dir_markdown_is_skipped() {
  local rel r err
  err="${TEST_TMP}/skip.err"
  for rel in \
    "202610/topic/topic__final_assets/README.md" \
    "202610/topic/topic__cld_assets/test.md" \
    "202610/topic/acceptance.md" \
    "202610/topic/pdfkit_table_selection_report_drafts.md"
  do
    : >"$CALLS_FILE"
    : >"$err"
    r="$(write_report "$rel")"
    HOOK_PROJECT="proj" run_capture "$r" >/dev/null 2>"$err"
    assert_same "0" "$?"
    assert_same "0" "$(create_call_count)"
    assert_contains "bob-research-capture: skip:" "$(cat "$err")"
    assert_contains "is not a research report" "$(cat "$err")"
  done
}

function test_hook_command_and_provider_use_intact() {
  assert_contains "sase-research-artifacts@research-highlights" "$(cat "$SASE_YML")"
  assert_contains "command: bob_research_capture" "$(cat "$SASE_YML")"
  if grep -q "bob ref create --include-id" "$SASE_YML"; then
    printf 'old hook command still present\n' >&2
    return 1
  fi
  local block
  block="$(python3 - "$SASE_YML" <<'PY'
import sys
text = open(sys.argv[1]).read()
start = text.index("file_hooks:")
end = text.index("github_orgs:")
print(text[start:end])
PY
)"
  assert_contains "use: sase-research-artifacts@research-highlights" "$block"
  if printf '%s' "$block" | grep -q "producers:"; then return 1; fi
  if printf '%s' "$block" | grep -q "path_globs:"; then return 1; fi
  if printf '%s' "$block" | grep -q "ops:"; then return 1; fi
}

# END HELPERS
