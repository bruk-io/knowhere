# C4 Decomposition Decision Tree

Use this guide when deciding whether and how to decompose architecture elements.

## Should I create a System Context diagram (Level 1)?

**Always yes.** Every software system should have at least one System Context diagram.

Ask:
- Who are the users of this system?
- What external systems does it integrate with?
- What external systems depend on it?

If you can't answer these questions, you don't understand the system well enough to model it.

## Should I create Container diagrams (Level 2)?

**Almost always yes**, unless the system is trivially simple (a single deployable with no external dependencies).

Ask:
- Does the system have more than one deployable unit?
- Does it use a database, message queue, or cache?
- Does it have separate frontend and backend?
- Are there multiple services?

If any answer is yes, create a Container diagram.

## Should I create Component diagrams (Level 3)?

**Optional.** The book recommends component diagrams as an optional level of detail to most engineering teams — but not all. Brown says "I wouldn't recommend it to all engineering teams."

Create Level 3 when:
- You are doing up-front design for a small to medium size application and want to sketch initial code structure (for larger applications, up-front component diagrams become tedious and time consuming — the book explicitly warns against this)
- You need long-lived documentation of a larger application's internal decomposition, and the benefit justifies the ongoing maintenance cost

Skip Level 3 when:
- The container is a single-purpose application with no non-trivial internal structure (e.g., a single-endpoint microservice)
- The container is a data store (database, file system, content store) — use entity relationship diagrams instead
- The internal structure changes frequently — component diagrams age rapidly as code evolves; weigh maintenance cost against benefit

## Should I create Code diagrams (Level 4)?

**Rarely.** The book is direct: "there are very few reasons to create code-level diagrams, because the questions... can usually be answered by looking at the code." For existing software, code diagrams are available on-demand from IDE tooling — prefer that over maintaining them as documentation artifacts.

Create Level 4 only when:
- The component is large and complicated enough that a visual summary adds clarity beyond reading the code
- You want to illustrate how a particular design pattern is implemented within a component

## Multi-System Landscapes

When modeling multiple systems:
1. Create a **System Landscape** view showing all systems and their relationships within the chosen scope (e.g. organisation, group, department, business function)
2. Create individual **System Context** diagrams for each system you own — landscape and context diagrams serve different purposes and are both needed
3. Decompose each system independently using the rules above

**System Landscape vs. System Context:**
- Landscape: broad map of ALL systems in scope — helps people understand the overall ecosystem
- Context: focused view of ONE system and its immediate neighbours — the entry point for deeper dives
- Audience for landscape: everyone, including senior stakeholders who want the "full picture"
- Audience for context: everyone involved with a specific system

## Signs You've Gone Too Deep

- Diagram has more than a handful of elements and has become cluttered (the book warns diagrams "start to become cluttered very quickly once you have more than a handful of components")
- You're showing classes or functions
- The diagram changes every sprint
- Nobody looks at it
- It takes more than 5 minutes to explain

## Signs You Haven't Gone Deep Enough

- Stakeholders ask "but how does it work?"
- New team members are confused about architecture
- Teams disagree about boundaries
- Integration points are unclear
