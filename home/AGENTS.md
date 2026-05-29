# athena - Bryan Bugyi's Home Server

IMPORTANT: You should not modify any of these memory files without approval from the user.

## Tier 1 (short-term) Memory

The following memory files contain core (always loaded) context:

<!-- sase-amd:short-memory:start -->

- @memory/short/sase.md
<!-- sase-amd:short-memory:end -->

## Tier 2 (dynamic) Memory

When a user prompt matches keywords from dynamic memories, we append a `### DYNAMIC MEMORY` section at the bottom of
that prompt listing individual `.sase/memory/` file paths — one per matched memory:

```
### DYNAMIC MEMORY
- @.sase/memory/long-facts-about-foobar.md (memory/long/facts_about_foobar, matched: `foobar facts`)
```

File names use a prefix that encodes the source tier: `long-` means the file originates from a long-term (tier 3) memory
source. If a `long-` prefixed file appears in your dynamic memory section, it contains the same content as the
corresponding tier 3 file below — you do NOT need to separately read the tier 3 file.

## Tier 3 (long-term) Memory

The below files contain detailed reference material. When working in their domain, you MUST use your `/sase_memory_read`
skill to review their contents. Do not read canonical `memory/long/*.md` files directly.

#### Long-Term Memory Files

<!-- sase-amd:long-memory:start -->

**`memory/long/obsidian.md`**  
Obsidian vault, notes workflow, and obsidian-headless/ob usage.

<!-- sase-amd:long-memory:end -->
