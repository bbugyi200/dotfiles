---
description: Legacy research swarm with initial, follow-up, and image agents.
input:
  - name: prompt
    type: text
    description: Research topic or question for the swarm to investigate.
---

%g:research {{ prompt }} #research

---

%w %g:research #fork #research/more %m:@default

---

%w %g:research #fork #research/image %m:gpt-5.5
