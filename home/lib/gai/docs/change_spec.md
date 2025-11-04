A ChangeSpec is a gai format specification for a CL (aka a PR). The format of a single ChangeSpec is as follows (without the backticks or comments):

```
NAME: <NAME>  // where <NAME> is the name of the CL
DESCRIPTION:
  <TITLE>  // where <TITLE> is a short description of the CL (2-spaces indented)
  
  <BODY>  // where <BODY> is a multi-line description of the CL (all lines 2-spaces indented)
PARENT: <PARENT>  // Either "None" or the CL-ID of the parent CL
CL: <CL>  // where <CL> is the CL-ID of the CL being described
STATUS: <STATUS>  // where <STATUS> is one of "Not Started", "In Progress", "Pre-Mailed", "Mailed", or "Submitted"
```
