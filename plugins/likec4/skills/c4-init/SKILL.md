---
name: c4-init
description: Scaffolds a new LikeC4 architecture project with C4 methodology directory structure including specification, models, views, and deployment directories. Use when initializing a C4 project, creating architecture diagrams from scratch, or setting up a LikeC4 workspace.
disable-model-invocation: true
argument-hint: "[system-name]"
allowed-tools: Bash, Write, Read, Glob
---

# Initialize a LikeC4 Architecture Project

Scaffold a new LikeC4 project following the C4 methodology directory structure.

## Steps

1. Ask the user for:
   - System name (if not provided as argument). Use kebab-case for the directory name.
   - Brief description of the system
   - Key actors/users of the system
   - Known external systems it integrates with

2. Determine the target directory. Default to `architecture/` in the current project root. Ask if the user wants a different location.

3. Check if `likec4` is available. If not, inform the user to install it:
   ```
   npm i -D likec4
   ```

4. Create the directory structure:
   ```
   architecture/
   ├── specification.likec4
   ├── models/
   │   └── <system-name>/
   │       ├── context.likec4
   │       └── containers/
   ├── views/
   │   ├── context/
   │   ├── containers/
   │   ├── components/
   │   ├── deployment/
   │   └── dynamic/
   └── deployment/
   ```

5. Generate `specification.likec4` with standard C4 element kinds:
   - actor (shape: person)
   - system
   - container
   - component
   - database (shape: storage)
   - queue (shape: queue)
   - Common relationship kinds: async, subscribes
   - Common tags: deprecated, next

6. Generate `models/<system-name>/context.likec4` with:
   - The actors the user described
   - The system itself
   - External systems mentioned
   - Placeholder relationships between them

7. Generate `views/context/<system-name>.likec4` with:
   - An index view showing the system context
   - Appropriate auto-layout

8. Print a summary of what was created and suggest next steps:
   - Run `npx likec4 dev` to preview
   - Add containers by creating files in `models/<system-name>/containers/`
   - Install C4 rules with `/c4-install-rules`
