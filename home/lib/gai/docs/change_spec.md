A ChangeSpec is a gai format specification for a CL (aka a PR). The format of a single ChangeSpec is as follows (without the backticks or comments):

```
NAME: <NAME>  // where <NAME> is the name of the CL
DESCRIPTION:
  <TITLE>  // where <TITLE> is a short description of the CL (2-spaces indented)

  <BODY>  // where <BODY> is a multi-line description of the CL (all lines 2-spaces indented)
PARENT: <PARENT>  // Either "None" or the CL-ID of the parent CL
CL: http://cl/<CL>  // where <CL> is the CL-ID of the CL being described
TEST TARGETS:  // Optional field. Either "None" (no tests required), or one or more bazel test targets, or omitted (tests required but targets TBD)
  // Formats supported:
  //   Single-line:  TEST TARGETS: //my/package:test1 //other:test2
  //   Multi-line:   TEST TARGETS:
  //                   //my/package:test1
  //                   //other/package:test2
  // Valid target format: //path/to/package:target_name
  // Multi-line format: each target on its own line, 2-space indented, no blank lines between targets
STATUS: <STATUS>  // where <STATUS> is one of "Blocked", "Not Started", "In Progress", "Failed to Create CL", "TDD CL Created", "Fixing Tests", "Failed to Fix Tests", "Pre-Mailed", "Mailed", or "Submitted"
  // "Blocked" means the ChangeSpec has a PARENT that has not reached "Pre-Mailed" status or beyond yet
```
