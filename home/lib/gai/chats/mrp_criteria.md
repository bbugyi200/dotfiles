# Merge-Readiness Pack (MRP) Criteria

A CL/PR is considered "merge-ready" when it provides clear evidence satisfying all five criteria below. The goal is to shift human review from auditing raw code to validating a structured evidence bundle.

## 1. Functional Completeness

**The Gap:** Agents often produce superficial or partial fixes that pass narrow tests but fail to address the holistic user need.

**Evidence Required:**
- [ ] End-to-end test results demonstrating the feature works in realistic scenarios
- [ ] All acceptance criteria from the task specification are addressed
- [ ] Edge cases and boundary conditions are handled
- [ ] The change solves the root problem, not just symptoms
- [ ] No regressions introduced to existing functionality

## 2. Sound Verification

**The Gap:** Agents may generate code that passes weak test suites, or fail to create robust tests for their own logic.

**Evidence Required:**
- [ ] All existing tests pass (`make test`)
- [ ] New test cases cover the added/modified code
- [ ] Test plan is documented (what scenarios are tested and why)
- [ ] Tests verify behavior, not just implementation details
- [ ] Test coverage meets or exceeds project threshold
- [ ] Tests are deterministic and reproducible

## 3. Exemplary SE Hygiene

**The Gap:** Agent-generated code can be functional but difficult to maintain, often violating style guides or fundamental engineering principles.

**Evidence Required:**
- [ ] All linting passes (`make lint`)
- [ ] Code formatting is consistent (`make fix` applied)
- [ ] No violations of project style guides
- [ ] DRY principle followed (no unnecessary duplication)
- [ ] SOLID principles respected where applicable
- [ ] Static analysis tools report no new issues
- [ ] Code complexity is reasonable (no overly nested logic)
- [ ] No introduction of technical debt

## 4. Clear Rationale and Communication

**The Gap:** An agent's reasoning is often buried in verbose logs that are impractical for humans to audit for high-level intent.

**Evidence Required:**
- [ ] Clear, human-readable summary of the change (PR description)
- [ ] Explanation of the approach taken
- [ ] Trade-offs considered and documented
- [ ] Alternative approaches mentioned if relevant
- [ ] Breaking changes clearly flagged
- [ ] Any assumptions or constraints documented

## 5. Full Auditability

**The Gap:** Due to agent non-determinism, running the same prompt twice may not yield the same result, making reproducibility challenging.

**Evidence Required:**
- [ ] Versioned links to exact prompts/scripts used
- [ ] Commit history is clean and logical
- [ ] Each commit has a clear, descriptive message
- [ ] Changes are atomic and focused (one logical change per CL)
- [ ] Diff is reviewable (no unrelated changes mixed in)
- [ ] Environment/tooling versions documented if relevant

---

## Quick Checklist Summary

Before submitting an MRP, verify:

1. **Functional Completeness** - Does it fully solve the problem?
2. **Sound Verification** - Are there adequate tests proving it works?
3. **Exemplary SE Hygiene** - Is the code clean and maintainable?
4. **Clear Rationale** - Would a reviewer understand why this approach?
5. **Full Auditability** - Can the work be traced and reproduced?

---

## References

Based on: Hassan et al., "Agentic Software Engineering: Foundational Pillars and a Research Roadmap" (Section 4.2.4: From Code Review to Evidence-Based Oversight)
