---
name: commit-note.agent
description: "The fixed commit-description request appended to every producing stage's prompt — the post-stage git hook records the agent's answer as the stage commit's message. A fragment, not a stage: it is never dispatched on its own and carries no stage binding."
role: fragment
---

COMMIT MESSAGE: end your final output with a single line 'COMMIT: <one line describing what this stage changed and why>' — the engine records it as this stage's git commit message.
