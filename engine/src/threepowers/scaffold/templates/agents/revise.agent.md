---
name: revise.agent
description: "The prompt block a human-gate revise injects into the re-dispatched stage — carries the gate, the artifact under review, and the human's feedback. A fragment, not a stage: it is never dispatched on its own and carries no stage binding. $GATE, $ARTIFACT, and $FEEDBACK are filled at assembly time."
role: fragment
---

REVISION REQUESTED (human gate '$GATE'): the artifact under review is $ARTIFACT. Apply the following human feedback and revise that artifact in place — keep everything the feedback does not name, and do not advance past this stage:
$FEEDBACK
