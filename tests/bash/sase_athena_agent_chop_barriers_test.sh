#!/bin/bash

#################################################################################
# Pin standalone-workflow agent chops and exclude them from drain barriers.     #
#################################################################################

ATHENA_CONFIG="${PWD}/home/dot_config/sase/sase_athena.yml"

function test_standalone_workflow_agent_chops_exclude_drain_barriers() {
  local actual
  actual="$("${PWD}/.venv/bin/python" - "${ATHENA_CONFIG}" <<'PY'
import sys
from pathlib import Path

import yaml


config = yaml.safe_load(Path(sys.argv[1]).read_text())
agent_chops = {}
for lumberjack in config["axe"]["lumberjacks"].values():
    for chop in lumberjack.get("chops", []):
        if "agent" in chop:
            agent_chops[chop["name"]] = chop["agent"]

standalone_refs = {
    "sase_core_refresh_docs": "#!sase/refresh_docs",
    "sase_github_refresh_docs": "#!sase/refresh_docs",
    "sase_nvim_refresh_docs": "#!sase/refresh_docs",
    "sase_recent_bug_audit": "#!sase/audit_recent_bugs",
    "sase_recent_improvement_audit": "#!sase/audit_recent_improvements",
    "sase_refresh_docs": "#!sase/refresh_docs",
    "sase_telegram_refresh_docs": "#!sase/refresh_docs",
}

for name, standalone_ref in standalone_refs.items():
    prompt = agent_chops[name]
    print(
        f"{name}\t{standalone_ref}\t{prompt.count(standalone_ref)}\t"
        f"{prompt.count('#!')}\t{prompt.count('%w(runners=0)')}"
    )

unexpected = sorted(set(agent_chops) - set(standalone_refs))
if unexpected:
    print(f"unexpected agent chops: {', '.join(unexpected)}")
PY
)"

  local expected
  expected=$'sase_core_refresh_docs\t#!sase/refresh_docs\t1\t1\t0\n'
  expected+=$'sase_github_refresh_docs\t#!sase/refresh_docs\t1\t1\t0\n'
  expected+=$'sase_nvim_refresh_docs\t#!sase/refresh_docs\t1\t1\t0\n'
  expected+=$'sase_recent_bug_audit\t#!sase/audit_recent_bugs\t1\t1\t0\n'
  expected+=$'sase_recent_improvement_audit\t#!sase/audit_recent_improvements\t1\t1\t0\n'
  expected+=$'sase_refresh_docs\t#!sase/refresh_docs\t1\t1\t0\n'
  expected+=$'sase_telegram_refresh_docs\t#!sase/refresh_docs\t1\t1\t0'

  assert_same "${expected}" "${actual}"
}
