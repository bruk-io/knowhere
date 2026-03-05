---
globs: ["**/landscape.likec4", "**/landscape.c4", "**/views/landscape/**/*.likec4", "**/views/landscape/**/*.c4"]
---

# C4 System Landscape Rules

You are editing a System Landscape file. This is a map of all software systems within a chosen scope.

## Purpose

A system landscape diagram shows the big picture across multiple software systems — a map of all software systems within a chosen scope (e.g. organisation, group, department, business function). It is NOT a replacement for individual system context diagrams.

## What Belongs Here
- All software systems within the chosen scope (owned and external)
- People/actors who interact with those systems
- Relationships between systems at a high level
- A clearly defined scope boundary (org, department, business function)

## What Does NOT Belong Here
- Containers, components, or technology details (those are for deeper diagrams)
- Internal structure of any system
- Infrastructure or deployment details

## Scope Boundary
- Be explicit about the scope: "All systems in the Payments domain", "All systems owned by Team X", "All systems in this business function"
- Valid scopes include: an entire organisation, a group, a department, or a business function
- Systems outside the scope but that interact with in-scope systems can appear de-emphasized

## Relationship Rules
- Describe WHAT the relationship does, not HOW (same as Level 1 context)
- Labels should be high-level: "Sends orders to", "Gets customer data from"
- No technology or protocol details needed

## Relationship to System Context Diagrams
- A landscape diagram shows EVERY system; a context diagram focuses on ONE system
- Use a landscape diagram to provide orientation, then create individual context diagrams for each system your team owns
- Link landscape views to individual context views using `navigateTo`

## Audience

Everyone — both technical and non-technical stakeholders, including senior stakeholders who want the full picture across multiple systems.

## Naming
- Name the view to reflect its scope: `organisationLandscape`, `paymentsDomainLandscape`
- Title should describe the scope: "System Landscape — Payments Domain"
