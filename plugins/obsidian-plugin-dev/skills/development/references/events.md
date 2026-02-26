# Event System Reference

Obsidian uses an event-driven architecture. Register events in `onload()` — they are automatically cleaned up on plugin unload.

## Vault Events

Fired when files are created, modified, deleted, or renamed.

```typescript
this.registerEvent(
  this.app.vault.on("create", (file) => {
    // File or folder created
  })
);

this.registerEvent(
  this.app.vault.on("modify", (file) => {
    // File content changed
  })
);

this.registerEvent(
  this.app.vault.on("delete", (file) => {
    // File or folder deleted
  })
);

this.registerEvent(
  this.app.vault.on("rename", (file, oldPath) => {
    // File or folder renamed/moved
  })
);
```

## Workspace Events

Fired when the user navigates, opens files, or changes the active view.

```typescript
this.registerEvent(
  this.app.workspace.on("file-open", (file) => {
    // A file was opened (file is null when no file is active)
  })
);

this.registerEvent(
  this.app.workspace.on("active-leaf-change", (leaf) => {
    // The active pane changed
  })
);

this.registerEvent(
  this.app.workspace.on("layout-change", () => {
    // Workspace layout was modified (panes opened/closed/moved)
  })
);

// Wait for workspace layout to be ready on startup
this.app.workspace.onLayoutReady(() => {
  // Safe to query workspace state here
});
```

## Editor Events

Fired when the user edits, pastes, or drops content into the editor.

```typescript
// React to editor content changes
this.registerEvent(
  this.app.workspace.on("editor-change", (editor, info) => {
    // Editor content was modified
  })
);

// Intercept paste events
this.registerEvent(
  this.app.workspace.on("editor-paste", (evt, editor, view) => {
    const text = evt.clipboardData?.getData("text/plain");
    if (text && shouldTransform(text)) {
      evt.preventDefault();
      editor.replaceSelection(transformText(text));
    }
  })
);

// Handle drag-drop into editor
this.registerEvent(
  this.app.workspace.on("editor-drop", (evt, editor, view) => {
    const files = evt.dataTransfer?.files;
    if (files?.length) {
      evt.preventDefault();
      // Handle dropped files
    }
  })
);
```

## Context Menu Events

Add items to file explorer and editor right-click menus.

```typescript
// File context menu (right-click on files in sidebar)
this.registerEvent(
  this.app.workspace.on("file-menu", (menu, file) => {
    menu.addItem((item) =>
      item
        .setTitle("My custom action")
        .setIcon("dice")
        .onClick(async () => {
          new Notice(`Action on: ${file.path}`);
        })
    );
  })
);

// Editor context menu (right-click in editor)
this.registerEvent(
  this.app.workspace.on("editor-menu", (menu, editor, view) => {
    menu.addItem((item) =>
      item
        .setTitle("Transform selection")
        .setIcon("wand")
        .onClick(() => {
          const selection = editor.getSelection();
          if (selection) {
            editor.replaceSelection(selection.toUpperCase());
          }
        })
    );
  })
);
```

## Metadata Cache Events

Fired when file metadata (frontmatter, tags, links) changes.

```typescript
this.registerEvent(
  this.app.metadataCache.on("changed", (file, data, cache) => {
    // A file's metadata cache was updated
  })
);

this.registerEvent(
  this.app.metadataCache.on("resolved", () => {
    // All pending metadata updates have been processed
  })
);
```

## DOM Events

Attach to DOM elements with automatic cleanup on unload.

```typescript
this.registerDomEvent(document, "click", (evt: MouseEvent) => {
  // Handle click
});
```

## Intervals

Register intervals with automatic cleanup on unload.

```typescript
this.registerInterval(
  window.setInterval(() => {
    // Runs every 5 minutes
  }, 5 * 60 * 1000)
);
```

## Debouncing Events

Use `debounce` from Obsidian for frequently firing events like `modify`.

```typescript
import { debounce } from "obsidian";

const debouncedSave = debounce(
  (file: TFile) => {
    // Process file change
  },
  500,
  true
);

this.registerEvent(
  this.app.vault.on("modify", debouncedSave)
);
```
