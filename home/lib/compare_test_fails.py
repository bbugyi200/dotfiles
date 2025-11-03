import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

# --- optional dependency (fallback if unavailable) ---
try:
    from rapidfuzz.fuzz import token_set_ratio
except Exception:

    def token_set_ratio(a: str, b: str) -> int:
        ta, tb = set(a.split()), set(b.split())
        if not ta and not tb:
            return 100
        inter = len(ta & tb)
        score = 200 * inter / (len(ta) + len(tb) or 1)  # symmetric
        return int(round(score))


# ------------------ normalization -------------------
NOISE_PATTERNS = [
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z",  # ISO ts
    r"\b\d+ms\b|\b\d+\.\d+s\b",  # durations
    r"0x[0-9a-fA-F]+",  # hex ptrs
    r"pid=\d+|tid=\d+",  # ids
    r"/tmp/[\w\-/\.]+",  # tmp paths
    r"seed=\d+",
    r"port=\d+",  # run noise
]
noise_re = re.compile("|".join(NOISE_PATTERNS))


def normalize(s: str) -> str:
    s = noise_re.sub("", s)
    # keep only filename for paths like ".../file.py:123"
    s = re.sub(
        r"(/[^:\s]+)+:(\d+)", lambda m: m.group(0).split("/")[-1].split(":")[0], s
    )
    s = re.sub(r"(\r?\n)+", "\n", s).strip()
    return s


# ------------------ fingerprinting ------------------
@dataclass(frozen=True)
class Fingerprint:
    test_id: str
    exc: str
    msg_hash: str
    topk_hash: str


def topk_frames(block: str, k: int = 3) -> tuple[str, ...]:
    frames = []
    for line in block.splitlines():
        # matches "in func" / "at pkg.module.func"
        m = re.search(r"(?:in |at )([\w\.]+)", line)
        if m:
            frames.append(m.group(1))
    return tuple(frames[:k])


def h(s: str) -> str:
    return hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest()


def extract_failures(
    doc: str,
) -> list[tuple[str, str, str, tuple[str, ...], Fingerprint, str]]:
    # generic splitters; adapt to pytest/junit/jest as needed
    blocks = re.split(
        r"\n={3,}.*?FAIL.*?={3,}\n|\n-+ FAIL -+\n", doc, flags=re.IGNORECASE
    )
    if len(blocks) == 1:
        blocks = re.split(r"\nFAIL(?:URES)?[: ]", doc, flags=re.IGNORECASE)

    failures = []
    for b in blocks:
        if re.search(r"AssertionError|Error|Exception|FAIL", b):
            tidm = re.search(
                r"(?m)^(?:FAIL|FAILED|Test)\s*[:\s]+([^\n]+)", b
            ) or re.search(r"(?m)^(\w+\.\w+\.\w+::\w+)|^(\w+::\w+::\w+)", b)
            test_id = ""
            if tidm:
                # prefer first non-None group
                test_id = next((g for g in tidm.groups() if g), "").strip()

            excm = (
                re.search(r"(\w+Error|\w+Exception|Timeout)", b)
                or re.search(r"AssertionError", b)
                or re.search(r"FAIL", b)
            )
            exc = excm.group(0) if excm else "UnknownFailure"

            msgm = re.search(
                r"(?s)(AssertionError:.*?$|Error:.*?$|Exception:.*?$)", b
            ) or re.search(r"(?s)^\s*E\s+.*$", b, re.M)
            msg = msgm.group(0) if msgm else b[:500]

            frames = topk_frames(b, 3)
            fp = Fingerprint(
                test_id=test_id, exc=exc, msg_hash=h(msg), topk_hash=h(">".join(frames))
            )
            failures.append((test_id or f"unknown_{h(b)[:6]}", exc, msg, frames, fp, b))
    return failures


# ------------------- comparison ---------------------
def compare_outputs(a_raw: str, b_raw: str) -> dict[str, Any]:
    a, b = normalize(a_raw), normalize(b_raw)
    a_fail = extract_failures(a)
    b_fail = extract_failures(b)

    a_by_test = defaultdict(list)
    b_by_test = defaultdict(list)
    for t in a_fail:
        a_by_test[t[0]].append(t)
    for t in b_fail:
        b_by_test[t[0]].append(t)

    a_tests, b_tests = set(a_by_test.keys()), set(b_by_test.keys())
    jaccard_tests = len(a_tests & b_tests) / (len(a_tests | b_tests) or 1)

    changed, same, fixed, new = [], [], [], []
    msg_sim_scores = []
    for test_id in a_tests | b_tests:
        if test_id in a_tests and test_id not in b_tests:
            fixed.append(test_id)
        elif test_id in b_tests and test_id not in a_tests:
            new.append(test_id)
        else:
            a_fp = a_by_test[test_id][0][4]
            b_fp = b_by_test[test_id][0][4]
            if a_fp == b_fp:
                same.append(test_id)
            else:
                changed.append(test_id)
                a_msg = a_by_test[test_id][0][2]
                b_msg = b_by_test[test_id][0][2]
                msg_sim_scores.append(token_set_ratio(a_msg, b_msg))

    exc_before, exc_after = (
        Counter([f[1] for f in a_fail]),
        Counter([f[1] for f in b_fail]),
    )

    total_before, total_after = len(a_fail), len(b_fail)
    fixed_w = 40 * len(fixed)
    count_w = 30 * (total_before - total_after)
    changed_w = 20 * sum(1 for s in msg_sim_scores if s < 70) + 10 * sum(
        1 for s in msg_sim_scores if 70 <= s < 90
    )
    jaccard_w = int(10 * (1 - jaccard_tests))
    score = max(0, min(100, fixed_w + count_w + changed_w + jaccard_w))

    return {
        "score": score,
        "tests_before": len(a_tests),
        "tests_after": len(b_tests),
        "failures_before": total_before,
        "failures_after": total_after,
        "jaccard_tests": round(jaccard_tests, 3),
        "fixed_tests": sorted(fixed),
        "new_tests": sorted(new),
        "unchanged_tests": sorted(same),
        "changed_tests": sorted(changed),
        "avg_changed_msg_similarity": (
            (sum(msg_sim_scores) / len(msg_sim_scores)) if msg_sim_scores else None
        ),
        "exception_hist_before": dict(exc_before),
        "exception_hist_after": dict(exc_after),
    }


# -------------------- CLI entry ---------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two test failure outputs to assess meaningful progress."
    )
    parser.add_argument(
        "before_path", help="Path to the earlier (baseline) test output file"
    )
    parser.add_argument("after_path", help="Path to the newer test output file")
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON with indentation"
    )
    args = parser.parse_args()

    try:
        with open(args.before_path, encoding="utf-8", errors="ignore") as f:
            before = f.read()
        with open(args.after_path, encoding="utf-8", errors="ignore") as f:
            after = f.read()
    except FileNotFoundError as e:
        print(f"File not found: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error reading files: {e}", file=sys.stderr)
        sys.exit(2)

    result = compare_outputs(before, after)
    if args.pretty:
        print(json.dumps(result, indent=2, sort_keys=False))
    else:
        print(json.dumps(result, separators=(",", ":")))

    # Optional exit codes that can be useful in CI (customize thresholds):
    # 0 = progress or neutral, 1 = regression
    if (
        result["failures_after"] > result["failures_before"]
        and not result["fixed_tests"]
    ):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
