---
description: Write a piece of work down as intent/<slug>/intent.md, in the requester's own words, and open it as a PR for them to accept. Run it when someone brings a problem to be worked on, or when a breached control band or a review finding needs to become work.
argument-hint: <slug>
arguments: [slug]
disable-model-invocation: true
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/artefact-check" *)
---

# Capture an intent

The intent is the loop's first artefact: the problem, the outcome wanted, who it
touches, what must hold, and what nobody knows yet, in the words of the person who has
the problem. Merging its PR accepts it, and the merge starts the spec.

The slug is `$slug`. If that is empty, choose a short kebab-case slug from the title.

1. With a person here, interview them until each part is concrete: the problem and its
   evidence, the outcome, the users and systems, the constraints, the unknowns. Keep
   their words; don't translate the problem into engineering terms. Show them the draft
   and let them correct it.
   With no person (a monitor or a CI job), the anomaly and its evidence are the
   problem, the affected systems are named, the proposed outcome is the fix, an action
   already taken gets its own line, and whatever the evidence can't settle is an open
   question.
2. Write `intent/<slug>/intent.md` from `${CLAUDE_PLUGIN_ROOT}/templates/intent.md`,
   with the status `draft`.
3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/artefact-check" intent/<slug>` and fix
   what it reports.
4. On a branch `intent/<slug>`, commit the file alone and open a PR that says merging
   it accepts the intent.

Stop there. The spec is the next play, and it starts when this merges.
