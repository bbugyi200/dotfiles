---
name: cl
---

### Context Files Related to this CL

- #x(cl_changes.diff, hg pdiff $(branch_changes | grep -v -E 'png$|fingerprint$') | perl -nE 'print s{google3/}{}gr') :
  Contains a diff of the changes made by the current CL.
- #x(cl_desc, cl_desc --short) : Contains the current CL's change description.
