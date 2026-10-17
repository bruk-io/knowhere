---
name: likec4-publish
description: Publish a LikeC4 model as an interactive Claude Artifact - the full LikeC4 viewer (view list, click-through drill-down, dynamic views, search, dark mode) as a private shareable page, instead of static PNGs. Use whenever the user asks to browse, explore, host, share, or "open interactively" a LikeC4 model or C4 diagrams, asks for an HTML artifact of the diagrams, or asks whether the LikeC4 server can be hosted for them. Also use to republish after the .c4 sources change.
argument-hint: "[likec4-project-dir]"
---

# Publish a LikeC4 model as an interactive artifact

`likec4 start` cannot be exposed from a Claude session, but `likec4 build` produces the same viewer as a static site, and the Artifact tool can host it. The result is one artifact URL that stays the same across republishes.

## Steps

1. **Validate and lint first.** The model must pass `npx likec4 validate <dir>` and, if the `likec4-diagrams` skill is in use, its `c4lint.py`. Publishing a model with errors publishes an empty viewer.

2. **Build the artifact files.**
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/likec4-publish/tools/build-artifact.py <likec4-project-dir> --title "<Name> C4" --verify
   ```
   The script runs `likec4 build --output-single-file`, splits the bundle into `index.html` (the page body), `app.js` and `app.css`, escapes the characters the Artifact validator rejects, and with `--verify` loads the result in headless Chromium and asserts the app mounted *and* its stylesheet applied. It prints the exact Artifact call to make. Do not hand-extract from the build output: the real stylesheet is in a `<style rel="stylesheet">` block that a naive `<style>` match misses, and a page without it renders as unstyled Times New Roman with the view list stacked down the left.

3. **Publish with the Artifact tool**, exactly as printed:
   - `file_path`: the `index.html` the script wrote
   - `files`: `{"app.js": "<outdir>/app.js", "app.css": "<outdir>/app.css"}` - relative paths, referenced from the page without a leading slash
   - first publish only: a `favicon` (an emoji) and one-sentence `description`; on republish omit both so the artifact keeps its identity
   - `title` comes from the page's `<title>`, which the script sets from `--title`

   Publish the split files, never the single-file build inline: the Artifact validator misidentifies a multi-megabyte inline page and refuses it.

4. **Republish to the same URL** by calling Artifact again with the same `file_path` in the same session, or with `url` from another session (read it first with `action: "read"`). Rebuild with the script before every republish; the artifact holds a snapshot, not a live link to the sources.

5. **Tell the user** what the page is in one sentence, and which of the viewer's features do not work inside the artifact sandbox: the export-to-PNG button and the Kroki/PlantUML integrations, which need outbound network. Everything else - navigation, drill-down, dynamic view playback, search, theme toggle, embedded fonts - is self-contained.

## When not to use this

- The user asked for images to paste into a document: use `npx likec4 export png` from the `likec4-diagrams` skill instead.
- The model is a one-off sketch the user will not revisit: PNGs, delivered with SendUserFile, are enough.
- The user wants the LikeC4 dev server with live reload on their own machine: tell them to run `npx likec4 start <dir>` locally; this skill produces a static snapshot.

## Requirements

Node.js with `npx` (the script fetches `likec4` on demand). `--verify` needs a Chromium: it looks under `$PLAYWRIGHT_BROWSERS_PATH`, then on `PATH`, and skips with a warning if none is found - in that case say so rather than claiming the page was verified.
