---
name: c4-export
description: Exports LikeC4 architecture diagrams as PNG images, JSON data, DrawIO files, or a static website. Validates the model before exporting. Use when exporting diagrams, building a C4 site, or generating artifacts from likec4 files.
disable-model-invocation: true
argument-hint: "[format: png|json|drawio|site]"
allowed-tools: Bash, Read, Glob
---

# Export Architecture Diagrams

Export LikeC4 architecture diagrams in various formats.

## Steps

1. If no format argument is provided, ask the user which format:
   - `png` - Export all views as PNG images
   - `json` - Export model as JSON data
   - `drawio` - Export as DrawIO diagrams
   - `site` - Build a static website with all views

2. Determine the source directory. Look for `architecture/` in the project root, or ask the user.

3. Check that `likec4` is available:
   ```bash
   npx likec4 --version
   ```

4. Run validation first:
   ```bash
   npx likec4 validate
   ```
   If validation fails, show errors and stop.

5. Run the appropriate export command:

   **PNG:**
   ```bash
   npx likec4 export png -o ./architecture/exports/png
   ```

   **JSON:**
   ```bash
   npx likec4 export json -o ./architecture/exports/model.json
   ```

   **DrawIO:**
   ```bash
   npx likec4 export drawio -o ./architecture/exports/drawio
   ```

   **Site:**
   ```bash
   npx likec4 build -o ./architecture/dist
   ```

6. Report what was exported and where.
