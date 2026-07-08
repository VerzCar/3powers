---
name: generic.agent
description: "The generic stage instruction used when a step has neither a repo-local nor a bundled stage template. A fragment, not a stage: it is never dispatched on its own and carries no stage binding. $STEP is filled with the step's name at assembly time."
role: fragment
---

STAGE: $STEP. Perform this lifecycle step for the intent below, staying within the spec's scope.
