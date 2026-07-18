---
description: Legacy research swarm with initial, follow-up, and image agents.
input:
  - name: prompt
    type: text
    description: Research topic or question for the swarm to investigate.
---

%t:research {{ prompt }} #research

---

%w %t:research #fork #research/more %m:@default

---

%w %t:research #fork #research/image %m:gpt-5.6-sol
