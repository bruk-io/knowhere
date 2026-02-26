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

**Only when it adds value.** This is where most people over-diagram.

Create Level 3 when:
- The container has complex internal structure that isn't obvious from its name
- Multiple teams work on the same container
- The container has been a source of confusion or bugs
- You need to plan a significant refactoring

Skip Level 3 when:
- The container follows a well-known pattern (standard MVC, simple CRUD API)
- The container is small enough to understand by reading code
- Only one developer works on it
- The internal structure changes frequently (the diagram will always be stale)

## Should I create Code diagrams (Level 4)?

**Almost never manually.**

Create Level 4 only when:
- Auto-generated from code (IDE tools, reverse engineering)
- Documenting a complex domain model for onboarding
- Planning a major rewrite of a critical component

Never create Level 4 when:
- You're doing it "for completeness"
- The code is the best documentation
- The component follows standard patterns

## Multi-System Landscapes

When modeling multiple systems:
1. Create a **System Landscape** view showing all systems and their relationships
2. Create individual **System Context** diagrams for each system you own
3. Decompose each system independently using the rules above

## Signs You've Gone Too Deep

- Diagram has more than 15-20 elements
- You're showing classes or functions
- The diagram changes every sprint
- Nobody looks at it
- It takes more than 5 minutes to explain

## Signs You Haven't Gone Deep Enough

- Stakeholders ask "but how does it work?"
- New team members are confused about architecture
- Teams disagree about boundaries
- Integration points are unclear
