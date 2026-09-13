# Poseidon Cargo cache (Athena)

Athena keeps disposable compiler results on `/mnt/poseidon` and ordinary Cargo
intermediates in SASE's managed temp tree. The 40 GiB sccache size is an LRU budget, not
a filesystem quota. SASE's managed-temp reaper is a **soft** retention policy: it is not
a hard cap and does not prove a build is idle.

## Effective paths

| Output                       | Location                                                                          |
| ---------------------------- | --------------------------------------------------------------------------------- |
| Compiler cache               | `/mnt/poseidon/sccache` (sccache disk backend, 40 GiB LRU)                        |
| sccache socket               | `/mnt/poseidon/sccache/sccache.sock`                                              |
| Ordinary Cargo intermediates | `~/.cache/sase/tmp/build-targets/cargo-{workspace-path-hash}`                     |
| Ordinary Cargo finals        | workspace-local `target/`                                                         |
| SASE launch outputs          | per-launch `~/.cache/sase/tmp/cargo-targets/<launch>`                             |
| Isolated dev-update/prebuild | `sase-core/target/uv-tool-py` and `uv-tool-lsp` (plus a `build/` dir beside each) |
| Retired shared target        | `/mnt/poseidon/cargo-target` (root-owned, mode 0555, empty)                       |

Identify Poseidon by mount `/mnt/poseidon` and UUID
`e0d96fde-be60-4f3b-bed7-3e9700060fdb`. Device names such as `/dev/sdc1` can change.

## Commands

sccache can cache `rlib` compilations. Hits were observed after deleting both the target
dir and the build-dir and rebuilding the same pair. Changing only `CARGO_TARGET_DIR` /
`CARGO_BUILD_BUILD_DIR` is a different `rustc --out-dir`, so it is a miss, not a cargo
no-op. Linked bins, cdylibs, and proc macros stay uncached.

```bash
# sccache stats (same config/socket as builds)
SCCACHE_CONF="$HOME/.config/sccache/config" \
  SCCACHE_DIR=/mnt/poseidon/sccache \
  SCCACHE_SERVER_UDS=/mnt/poseidon/sccache/sccache.sock \
  sccache --show-stats

# watcher
systemctl --user status poseidon-cache-watch.timer
journalctl --user -u poseidon-cache-watch.service -n 50

# TRIM / SMART (existing jobs; do not replace them)
systemctl status fstrim.timer
systemctl status prometheus-node-exporter-smartmon.timer
```

## Overrides

Uncached compile, full debug, incremental on:

```bash
RUSTC_WRAPPER='' CARGO_INCREMENTAL=1 \
  CARGO_PROFILE_DEV_DEBUG=2 CARGO_PROFILE_TEST_DEBUG=2 \
  cargo test
```

A `CARGO_TARGET_DIR` override relocates final artifacts only. Intermediates still follow
`build.build-dir` unless you also set `CARGO_BUILD_BUILD_DIR`. To move a whole tree:

```bash
CARGO_TARGET_DIR=/tmp/demo-target CARGO_BUILD_BUILD_DIR=/tmp/demo-build cargo build
cargo clean   # honors the selected pair
```

SASE launches always assign a fresh target and a matching build-dir. An explicit empty
`CARGO_BUILD_BUILD_DIR` keeps Cargo's own meaning of that override.

## Unexpected usage

1. Confirm Poseidon UUID and `df` available bytes (ordinary-user view).
2. Check whether `/mnt/poseidon/cargo-target` is writable or nonempty.
3. Check sccache dir/size/socket against the managed config.
4. Check managed scratch under `$SASE_TMPDIR` (`~/.cache/sase/tmp`) separately. Growth
   there is a soft-retention issue, not something sccache can purge.

## Rollback

Rollback restores the recorded Cargo config and disables the new watcher and wrapper. It
must **not** automatically restore the unbounded global Poseidon target.

1. `systemctl --user disable --now poseidon-cache-watch.timer`
2. Comment out or remove `build.rustc-wrapper` from `~/.cargo/config.toml`.
3. Restore the dated backup under
   `~/.local/share/sase-host-backups/20260913-poseidon-cargo/cargo-config.toml` **after
   deleting `target-dir = "/mnt/poseidon/cargo-target"`** unless you are intentionally
   performing the migration below.
4. `chezmoi apply` from a tree that no longer contains the Athena Cargo files, or ignore
   those paths.

Reopening `/mnt/poseidon/cargo-target` as a writable shared target is an explicit
migration (`chown`/`chmod` plus a `target-dir` line), not routine rollback. Do not
delete source, installed tools, or final artifacts.

Pre-change backup: `~/.local/share/sase-host-backups/20260913-poseidon-cargo/`.
