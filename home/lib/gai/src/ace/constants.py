"""Constants used across the ace package."""

# Default time in seconds after which a hook or workflow is considered a zombie (2 hours)
DEFAULT_ZOMBIE_TIMEOUT_SECONDS = 2 * 60 * 60

# Required hooks that are always added to new ChangeSpecs (order matters)
# - "!" prefix: skip fix-hook hints on failure
# - "$" prefix: skip running for proposal entries (e.g., "1a")
REQUIRED_CHANGESPEC_HOOKS = (
    "!$bb_hg_presubmit",
    "$bb_hg_lint",
)
