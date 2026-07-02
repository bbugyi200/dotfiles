---
create_time: 2026-07-02 10:47:52
status: done
prompt: sdd/prompts/202607/remove_idle_tracking.md
---

# Remove the User Idle / Activity-Tracking System

## Summary

SASE currently tracks user activity in the ACE TUI (keypress timestamps, an auto-idle threshold, manual idle via `I`,
pinned idle via `,I`) so that external consumers — in practice only the sase-telegram outbound chop — could suppress
Telegram notifications while the user is at the TUI. This never worked reliably, and in practice the user always runs
with pinned IDLE (`,I`) enabled, which makes `is_idle()` return `True` unconditionally and therefore makes the Telegram
gate a no-op.

This plan removes the idle/activity-tracking system completely from `sase` and `sase-telegram`, while preserving the
current _pinned-IDLE_ behavior exactly: **the Telegram outbound chop always sends eligible notifications,
unconditionally**. The only other consumer of the activity machinery — the TUI's deferred Tier-2 reconcile, which waits
for input quiescence before running a heavy full-history scan — keeps its behavior via a minimal in-memory input
timestamp that has no disk persistence, no UI, and no idle semantics.

`sase-core` (Rust) requires **no changes**: an exhaustive sweep confirmed the idle system has zero footprint there (all
lexical matches are unrelated subsystems — see "Do NOT touch" below).

## Background: how the system works today

**State files** (all under `sase_home()`, i.e. `~/.sase/`), owned by `src/sase/ace/tui_activity.py`:

| File                | Purpose                                                               |
| ------------------- | --------------------------------------------------------------------- |
| `tui_last_activity` | Last-activity epoch; `0` is a sentinel meaning "manually/pinned idle" |
| `tui_last_keypress` | True last-keypress epoch (never overwritten on idle transitions)      |
| `tui_idle_state`    | Authoritative `0`/`1` idle flag written by the TUI                    |
| `tui_pid`           | TUI process PID, used to detect a crashed/stale TUI                   |
| `tui_pinned_idle`   | Persisted pinned-idle flag, restored on TUI restart                   |

**Producers** (all in the ACE TUI):

- `_startup_mount.py` — writes the PID file on mount; restores pinned idle from disk (badge + epoch-0 marker) or writes
  a fresh "active" state.
- `_event_activity.py` (`EventActivityMixin`) — the 1-second countdown tick flushes keypress/PID/activity files every 10
  s and runs `_check_idle_state()` (auto-idle after `ace.inactive_seconds`, default 600).
- `_event_keyboard.py` and `navigation/_basic.py` — call `_record_user_activity()` on input to reset the idle timer and
  flush "active" state to disk on idle→active transitions.
- `lifecycle.py` — `action_mark_inactive` (`I`), `action_mark_inactive_pinned` (`,I`), and quit-time state cleanup
  (pinned idle survives quit; otherwise state files are removed).

**UI surfaces**: `InactiveIndicator` top-bar badge (orange IDLE / red ■ IDLE), the Activity Dashboard modal (`,i`,
backed by the in-memory `ActivityLog` of idle↔active transitions), command-palette entries, leader/footer hints, and
help-modal rows on all three tabs.

**Consumer** (the reason the system exists): `sase-telegram`'s outbound chop
(`src/sase_telegram/scripts/sase_tg_outbound.py`) imports `sase.ace.tui_activity.is_idle` from the host sase install and
gates sends on it twice — an early-exit in `main()` (`reason="user_active"`) and a per-notification re-check that breaks
the send loop if the user becomes active mid-batch (`stopped_active` counter). It also imports the state-file path
constants purely for a best-effort diagnostics log line. When IDLE is pinned, `is_idle()` is always `True`, both gates
always pass, and every eligible notification is sent.

**Incidental consumer**: `_maybe_trigger_idle_tier2_reconcile()` (`actions/agents/_loading_refresh.py`) defers the ~2.7
s full-history agent reconcile until `_last_activity_time` has been quiet for a threshold — a TUI-perf concern that
merely reuses the activity timestamp. The stall-watchdog diagnostics context (`_tui_stall_context()` in
`_startup_mount.py`) also reports `last_keypress_age_s` and the current activity-log state.

## Target behavior (invariants)

1. The Telegram outbound chop sends every eligible notification (unread, non-silent, newer than the high-water mark) on
   every run — identical to today's behavior with IDLE pinned. The HWM / `read` / `silent` filters are untouched.
2. No `~/.sase/tui_*` activity state files are ever written or read again; `sase.ace.tui_activity` no longer exists.
3. No IDLE badge, no `I` / `,I` / `,i` bindings, no Activity Dashboard, no `ace.inactive_seconds` config.
4. The Tier-2 reconcile still defers until input has been quiet (same threshold, same "armed users who never touch input
   still get the reconcile" semantics) — no TUI-perf regression.
5. Stale keymap/config entries in user configs (e.g. a leader `mark_inactive_pinned` override) degrade gracefully
   (dropped/warned), never crash startup.

## Landing order (cross-repo constraint)

The outbound chop resolves `sase.ace.tui_activity` from the **host sase install** at call time. If sase removes the
module before the plugin stops importing it, every outbound run crashes with `ImportError`. Therefore:

1. **Phase 1 (sase-telegram) merges and deploys first** — after it, the plugin has zero references to
   `sase.ace.tui_activity` and behaves identically to pinned IDLE.
2. **Phase 2 (sase) merges second** — removes the module and all TUI machinery.

Phase 1 is also safe against the _old_ sase: it simply stops calling `is_idle()`, which is behavior-compatible with the
pinned state the user already runs in.

Use `sase workspace open -p sase-telegram -r "<reason>" <workspace_num>` to obtain the sase-telegram working copy (where
`<workspace_num>` is the number assigned to the primary sase workspace you were started in).

## Phase 1 — sase-telegram: remove the idle gate

All in `src/sase_telegram/scripts/sase_tg_outbound.py` unless noted:

- Delete the `is_idle()` wrapper (lines ~56–59) and both gates:
  - the `main()` early-exit (`if not is_idle(): _print_outbound_summary(reason="user_active"...); return 0`, ~319–324),
  - the per-notification re-check + `break` in the send loop (~369–374).
- Remove the `stopped_active` plumbing end-to-end: the `stopped_active_count` parameter and summary field in
  `_print_outbound_summary` (~284, ~298), its initialization (~367), increment (~373), and the call-site argument
  (~522). The summary line simply drops the `stopped_active=` field and the `user_active` reason.
- In `_log_send_diagnostics` (~215–262): remove the imports of `ACTIVITY_FILE` / `IDLE_STATE_FILE` /
  `LAST_KEYPRESS_FILE` / `PID_FILE` and the corresponding `idle_state` / `pid` / `last_activity` / `last_keypress`
  diagnostic fields. Keep the rest of the diagnostics log intact.
- `src/sase_telegram/outbound.py`: update the module docstring (line 1, "detect inactivity...") and the HWM design
  comment (~22–29) that justifies not filtering dismissed notifications with "the outbound only runs when idle" —
  restate the rationale without the idle premise (the HWM semantics themselves do not change).
- Tests:
  - Delete `test_exits_early_when_user_active` (`tests/test_integration.py` ~110–120) — it tests the removed gate.
  - Strip every `patch(".../sase_tg_outbound.is_idle", return_value=True)` (decorator or context manager) and its
    injected mock argument from the remaining tests: `tests/test_integration.py` (~123, 140, 155, 190, 240, 282,
    344, 391) and `tests/test_outbound.py` (~289, 337, 404, 483; comment at ~92). The patch targets stop existing, so
    leaving any behind fails at patch time.
- Docs: `README.md` (lines ~11, 76, 109–110, 117 — "activity-aware sending", "only sends when inactive", "idle detection
  is handled by sase's TUI"), `docs/architecture.md` (~40), `docs/outbound.md` (~3, 17, 20). Reframe the outbound
  description as "sends unread notifications to Telegram" without the inactivity qualifier. Do NOT touch the
  "presence-based" wording in `README.md:142` / `docs/inbound.md:73` — that describes an env-var _presence_ check for
  agent launching, unrelated to user presence.

## Phase 2 — sase: remove the tracking system

### 2a. Core module and its runtime wiring

- Delete `src/sase/ace/tui_activity.py` (all five state files, `is_idle()`, guards) and its suite
  `tests/test_tui_activity.py`.
- `_event_activity.py`: the countdown tick must survive — it also drives the info-panel updates, axe live tick,
  starting-agent polls, and the Tier-2 reconcile trigger. Remove only the activity concerns: the 10 s
  keypress/PID/activity flush block and `_check_idle_state()`. Fold what remains into the countdown-tick home (either
  keep the mixin under a truthful name or merge the tick into an adjacent event mixin — implementer's choice; keep the
  tick's per-second cost profile unchanged).
- Replace `_record_user_activity()` with a minimal input-timestamp recorder (e.g. `_record_input_event()` setting
  `self._last_input_mono = time.monotonic()`), in-memory only:
  - callers to update: `_event_keyboard.py` (2 sites), `navigation/_basic.py` (2 sites), and the abstract stub in
    `_event_base.py`;
  - `_maybe_trigger_idle_tier2_reconcile()` (`agents/_loading_refresh.py` ~337–368) reads the new timestamp instead of
    `_last_activity_time` — its `max(last_input, armed_at)` deferral semantics stay identical;
  - `_tui_stall_context()` (`_startup_mount.py` ~153–170) keeps `last_keypress_age_s` from the new timestamp (useful
    stall diagnostics) and drops the `activity_state` field.
- `_startup_mount.py` (~99–138): remove the pinned-idle restore, all state-file writes, and the PID write; keep the
  stall-watchdog and countdown/auto-refresh timer setup. Initialize the new input timestamp here.
- `lifecycle.py`: remove `action_mark_inactive`, `action_mark_inactive_pinned`, the `write_quit_activity_state` quit
  step, and the `_pinned_idle` / `_activity_log` attribute threads.
- `_state_init.py` (~187–192): remove `_last_activity_time` / `_last_activity_flush` / `_pinned_idle` / `_activity_log`
  initialization (add the new input-timestamp init). `_state_init_late.py` (~94–101): remove the `ace.inactive_seconds`
  config read. Remove the matching attribute type hints in `startup.py` (~65–68) and `_event_base.py` (~47–50).
- `repro/replay.py` (~171–179): drop the `tui_activity` no-op patches from the replay harness.

### 2b. UI surfaces

- Delete `widgets/inactive_indicator.py`; remove its export from `widgets/__init__.py`, the
  `yield InactiveIndicator(id="inactive-indicator")` in `app.py` compose (+ import), and the `#inactive-indicator` rule
  in `styles.tcss`.
- Delete `activity_log.py` (`ActivityLog` / `ActivityEventType`) and `modals/activity_modal.py`; remove the
  `ActivityModal` export from `modals/__init__.py`; remove `_show_activity_dashboard()` and the `_activity_log` /
  `_inactive_seconds` hints from `actions/agent_workflow/_mentor_review.py`.
- `actions/agent_workflow/_leader_mode.py` (~184–194): remove the `,i` (activity dashboard) and `,I` (pinned idle)
  dispatch arms.

### 2c. Keymaps, commands, config

- App-level `mark_inactive`: remove the `AppKeymaps` field (`keymaps/types.py:303`), the `_BINDING_META` row
  (`types.py:91`), the static binding (`bindings.py:83`), the default (`default_config.yml:98`), and the command-palette
  metadata row (`commands/_app_metadata.py:129`). Stale user overrides are already warned-and-ignored by the loader's
  unknown-key handling.
- Leader keys: remove `mark_inactive_pinned` / `activity_info` from the leader defaults (`keymaps/types.py:444–445`,
  `default_config.yml:211–212`) and **add both to `_RETIRED_LEADER_KEYS`** in `keymaps/loader.py` (the established
  retirement pattern), updating the comment block (the existing retired `mark_inactive` entry's "moved to app-level `I`"
  note becomes "removed").
- `commands/_mode_commands.py`: remove the two descriptions (~74–75) and the `mark_inactive_pinned` scope (~108).
- Footer/leader hints: `widgets/_keybinding_modes.py` rows for `activity_info` (~245) and `mark_inactive_pinned` (~248).
- Help modal rows on all three tabs: `modals/help_modal/agents_bindings.py` (~180–182, 292–296), `axe_bindings.py`
  (~84–86, 135–139), `changespecs_bindings.py` (~210–212, 274–278). Per repo convention, the help popup must stay in
  sync with removed functionality.
- Config: remove `ace.inactive_seconds` from `default_config.yml` (line 29).

### 2d. Docs

- `docs/ace.md`: delete the "## Idle Detection" section (~1156–1169) and the keybinding-table rows for `,I` (~663), `,i`
  (~889), and `I` (~891).
- `docs/configuration.md`: remove the `inactive_seconds` sample line (~195), the config-table row (~234), and the
  idle-keybinding/`is_idle()` prose (~241–242).

### 2e. Tests (beyond the two deleted suites)

- Delete `tests/test_activity_log.py`.
- `tests/test_keymaps_defaults.py:32–39` — remove/replace the test asserting `I` / leader-`I` defaults.
- `tests/test_command_catalog.py:303` and `tests/test_command_palette_wiring.py:338` — drop the `leader.activity_info`
  assertions/usage (rewire the palette-execution test to another leader command).
- Harness plumbing that patches `tui_activity` (patch targets disappear — patches must be removed, test intent kept):
  `tests/ace/tui/visual/_ace_png_snapshot_helpers.py` (~426, 475–503, including the bound-patch assertion),
  `tests/ace/tui/models/test_loader_executor_shutdown.py` (~11, 175, 191–205, incl. `app._pinned_idle` seeding),
  `tests/test_agent_group_revival_e2e.py` (~347, 407–414).
- `tests/ace/tui/test_top_bar_order.py:19` — remove `"inactive-indicator"` from the expected top-bar widget order.
- `tests/xprompt/test_snippet_config_yaml.py` (~60, 71) — update sample-config literals containing
  `inactive_seconds: 600`.
- No PNG goldens render the IDLE badge (the visual harness stubs the system out), so no snapshot regeneration is
  expected; if any top-bar golden shifts, inspect `.pytest_cache/sase-visual/` before accepting updates.

## Phase 3 — follow-ups (outside these two repos)

- **Chezmoi global config**: the `tg_outbound` chop description in the chezmoi-managed sase config reads "Send unread
  notifications to Telegram when user is inactive" — update the description text (drop "when user is inactive"). No
  functional keys change (the chop entry itself stays).
- **Stale state files**: after Phase 2 deploys, the five `~/.sase/tui_*` files are orphaned. One-time manual cleanup:
  `rm -f ~/.sase/tui_last_activity ~/.sase/tui_last_keypress ~/.sase/tui_idle_state ~/.sase/tui_pid ~/.sase/tui_pinned_idle`.
  No permanent migration code is warranted for a single-user tool.

## Do NOT touch (lexical lookalikes confirmed unrelated)

- `NavigationGate` (`tui/util/nav_gate.py`, `time_until_idle`, `is_navigating`) — j/k burst quiescence for refresh
  deferral, plus its tests (`test_nav_gate.py`, `test_post_launch_jk_lag.py`).
- `wait_for_visual_idle(...)` in visual tests — widget settling, not user idle.
- `PIDLESS_SCRIPT_CHOP_STALE_FALLBACK_SECONDS` / `include_pidless_as_dismissable` ("p-idle-ss") in axe/agent-cleanup.
- Agent "activity" labels (`WorkflowStateWire.activity`, agent-row progress text) and widget loading/idle states.
- Prompt-stash pinning, agent pinning, and workspace-claim `PINNED` tokens (sase and sase-core).
- Inactive _projects_ / inactive _panes_ wording (lifecycle states, snapshot names).
- sase-core in its entirety, and the "presence-based" env-var check in sase-telegram inbound docs.

## Validation

- **sase-telegram**: run the plugin's lint/test suite; verify the outbound entry point (`sase_chop_tg_outbound`) imports
  and dry-runs cleanly with no `sase.ace.tui_activity` reference anywhere
  (`grep -rn 'tui_activity\|is_idle' src tests docs README.md` must be empty).
- **sase**: `just install` first (ephemeral workspace), then `just check`. Targeted suites worth running directly:
  `tests/test_keymaps_defaults.py`, `tests/test_command_catalog.py`, `tests/test_command_palette_wiring.py`,
  `tests/ace/tui/test_top_bar_order.py`, `tests/ace/tui/models/test_loader_executor_shutdown.py`,
  `tests/test_agent_group_revival_e2e.py`, and the visual suite (`just test-visual`).
- Repo-wide reference sweep in sase:
  `grep -rniE 'tui_activity|is_idle|pinned_idle|mark_inactive|inactive_seconds|InactiveIndicator|inactive-indicator|ActivityLog|ActivityModal|activity_info|IDLE_AUTO|IDLE_MANUAL|IDLE_PINNED' src tests docs`
  should return only the documented lookalikes above.
- End-to-end sanity: launch `sase ace`, confirm the top bar renders without the badge slot, `I` and `,I` / `,i` do
  nothing (or are reported unknown), help modals show no idle rows, and a notification created while the TUI is open and
  focused still reaches Telegram on the next outbound chop run.
