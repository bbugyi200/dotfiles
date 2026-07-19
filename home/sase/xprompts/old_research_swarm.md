---
description: Legacy research swarm with initial, follow-up, and image agents.
input:
  - name: prompt
    type: text
    description: Research topic or question for the swarm to investigate.
---

%id(tribe=research) {{ prompt }} #research

---

%w %id(tribe=research) #fork #research/more %m:@default

---

%w %id(tribe=research) #fork #research/image %m:gpt-5.6-sol
