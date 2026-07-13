#!/bin/bash

#################################################################################
# Pin drain barriers on every agent-backed chop in the Athena overlay.          #
#################################################################################

ATHENA_CONFIG="${PWD}/home/dot_config/sase/sase_athena.yml"

function test_all_agent_backed_chops_have_exactly_one_drain_barrier() {
  local actual
  actual="$("${PWD}/.venv/bin/python" - "${ATHENA_CONFIG}" <<'PY'
import sys
from pathlib import Path

import yaml


config = yaml.safe_load(Path(sys.argv[1]).read_text())
agent_chops = []
for lumberjack in config["axe"]["lumberjacks"].values():
    for chop in lumberjack.get("chops", []):
        if "agent" in chop:
            agent_chops.append((chop["name"], chop["agent"]))

for name, prompt in sorted(agent_chops):
    print(f"{name}\t{prompt.count('%w(runners=0)')}")
PY
)"

  local expected
  expected=$'sase_core_refresh_docs\t1\n'
  expected+=$'sase_github_refresh_docs\t1\n'
  expected+=$'sase_nvim_refresh_docs\t1\n'
  expected+=$'sase_recent_bug_audit\t1\n'
  expected+=$'sase_recent_improvement_audit\t1\n'
  expected+=$'sase_refresh_docs\t1\n'
  expected+=$'sase_telegram_refresh_docs\t1\n'
  expected+=$'sase_toobig_split\t1'

  assert_same "${expected}" "${actual}"
}
