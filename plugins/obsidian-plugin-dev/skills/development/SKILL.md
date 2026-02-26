---
name: development
description: "This skill should be used when the user is working with Obsidian plugin code, asks about \"obsidian plugin API\", \"obsidian command\", \"obsidian modal\", \"obsidian suggest modal\", \"obsidian editor suggest\", \"obsidian autocomplete\", \"obsidian settings tab\", \"obsidian ribbon icon\", \"obsidian status bar\", \"obsidian notice\", \"obsidian view\", \"obsidian editor extension\", \"obsidian CodeMirror\", \"obsidian context menu\", \"obsidian right-click menu\", \"obsidian CSS variables\", \"obsidian styling\", \"registerEvent\", \"addCommand\", \"obsidian workspace\", \"obsidian vault API\", \"obsidian file operations\", \"obsidian markdown processing\", \"obsidian protocol handler\", \"obsidian loadData\", \"obsidian saveData\", \"obsidian data.json\", \"obsidian metadataCache\", \"obsidian event system\", \"obsidian editor-paste\", \"obsidian editor-drop\", or mentions Obsidian plugin development patterns, API usage, or extending Obsidian functionality."
---

# Obsidian Plugin Development Reference

Comprehensive reference for building Obsidian plugins with the Plugin API. For detailed event system reference, see `references/events.md`. For CSS variables and theming, see `references/styling.md`.

## Plugin Lifecycle

```typescript
import { Plugin } from "obsidian";

export default class MyPlugin extends Plugin {
  async onload() {
    // Called when plugin loads. Register all resources here.
  }

  onunload() {
    // Called when plugin unloads. Cleanup handled automatically
    // for resources registered with registerEvent, registerDomEvent, etc.
  }

  onUserEnable() {
    // Called after user explicitly enables the plugin.
    // Safe to show UI prompts (Notice, Modal) here.
    // Available since Obsidian 1.7.2
  }

  onExternalSettingsChange() {
    // Called when data.json is modified externally (e.g. sync).
    // Reload settings here if needed. Available since 1.5.7
  }
}
```

## Commands

Use `callback` for simple commands. Use `editorCallback` when the command only makes sense with an active editor. Use `checkCallback` when command availability depends on runtime conditions.

```typescript
// Simple command
this.addCommand({
  id: "my-command",
  name: "Do something",
  callback: () => {
    new Notice("Done!");
  },
});

// Editor command (only available when editor is active)
this.addCommand({
  id: "insert-text",
  name: "Insert text at cursor",
  editorCallback: (editor: Editor, view: MarkdownView) => {
    editor.replaceSelection("Inserted text");
  },
});

// Conditional command (shown only when check passes)
this.addCommand({
  id: "conditional-command",
  name: "Only when file is open",
  checkCallback: (checking: boolean) => {
    const view = this.app.workspace.getActiveViewOfType(MarkdownView);
    if (view) {
      if (!checking) {
        new Notice(`Editing: ${view.file?.name}`);
      }
      return true;
    }
    return false;
  },
});

// Remove a dynamically added command (since 1.7.2)
this.removeCommand("my-command");
```

**Important:** Never set default hotkeys — let users configure their own to avoid conflicts.

## Notices

```typescript
// Basic notice (auto-dismisses after ~4.5 seconds)
new Notice("Operation completed!");

// Notice with custom duration (milliseconds, 0 = stays until dismissed)
new Notice("Check this out!", 10000);

// Notice with DocumentFragment for rich content
const fragment = document.createDocumentFragment();
fragment.createEl("strong", { text: "Bold text" });
fragment.appendText(" and normal text");
new Notice(fragment);
```

## Context Menus

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

## UI Elements

### Ribbon Icon

```typescript
const ribbonEl = this.addRibbonIcon("dice", "My Plugin", (evt: MouseEvent) => {
  new Notice("Ribbon clicked!");
});
ribbonEl.addClass("my-plugin-ribbon");
```

### Status Bar (Desktop Only)

```typescript
const statusBarEl = this.addStatusBarItem();
statusBarEl.setText("My Plugin Active");
```

### Settings Tab

```typescript
import { App, PluginSettingTab, Setting } from "obsidian";

class MySettingTab extends PluginSettingTab {
  plugin: MyPlugin;

  constructor(app: App, plugin: MyPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    new Setting(containerEl)
      .setName("My setting")
      .setDesc("Description of the setting")
      .addText((text) =>
        text
          .setPlaceholder("Enter value")
          .setValue(this.plugin.settings.mySetting)
          .onChange(async (value) => {
            this.plugin.settings.mySetting = value;
            await this.plugin.saveSettings();
          })
      );
  }
}

// Register in onload():
this.addSettingTab(new MySettingTab(this.app, this));
```

**Settings UI guidelines:**
- Only use headings if you have multiple sections
- Use sentence case for labels ("Template folder location" not "Template Folder Location")
- Use `setHeading()` not HTML heading elements
- Omit redundant words ("Advanced" not "Advanced settings")

## Modals

### Basic Modal

```typescript
import { App, Modal } from "obsidian";

class MyModal extends Modal {
  constructor(app: App) {
    super(app);
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.setText("Hello from modal!");
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}

// Open modal:
new MyModal(this.app).open();
```

### Suggest Modal (Fuzzy Search)

Use `SuggestModal` for simple selection lists. Use `FuzzySuggestModal` when you want built-in fuzzy matching with highlighting.

```typescript
import { App, SuggestModal } from "obsidian";

interface Item {
  title: string;
  description: string;
}

class ItemSuggestModal extends SuggestModal<Item> {
  items: Item[];
  onChoose: (item: Item) => void;

  constructor(app: App, items: Item[], onChoose: (item: Item) => void) {
    super(app);
    this.items = items;
    this.onChoose = onChoose;
  }

  getSuggestions(query: string): Item[] {
    return this.items.filter((item) =>
      item.title.toLowerCase().includes(query.toLowerCase())
    );
  }

  renderSuggestion(item: Item, el: HTMLElement) {
    el.createEl("div", { text: item.title });
    el.createEl("small", { text: item.description });
  }

  onChooseSuggestion(item: Item, evt: MouseEvent | KeyboardEvent) {
    this.onChoose(item);
  }
}
```

```typescript
import { App, FuzzySuggestModal } from "obsidian";

class FileSuggestModal extends FuzzySuggestModal<TFile> {
  getItems(): TFile[] {
    return this.app.vault.getMarkdownFiles();
  }

  getItemText(file: TFile): string {
    return file.path;
  }

  onChooseItem(file: TFile, evt: MouseEvent | KeyboardEvent) {
    new Notice(`Selected: ${file.path}`);
  }
}
```

### Editor Suggest (Inline Autocomplete)

Use `EditorSuggest` to provide inline suggestions while the user types in the editor. Register with `this.registerEditorSuggest()`.

```typescript
import {
  Editor,
  EditorPosition,
  EditorSuggest,
  EditorSuggestContext,
  EditorSuggestTriggerInfo,
  TFile,
} from "obsidian";

class TagSuggest extends EditorSuggest<string> {
  plugin: MyPlugin;

  constructor(plugin: MyPlugin) {
    super(plugin.app);
    this.plugin = plugin;
  }

  onTrigger(
    cursor: EditorPosition,
    editor: Editor,
    file: TFile | null
  ): EditorSuggestTriggerInfo | null {
    const line = editor.getLine(cursor.line);
    const sub = line.substring(0, cursor.ch);
    // Trigger on "#" character
    const match = sub.match(/#(\w*)$/);
    if (match) {
      return {
        start: { line: cursor.line, ch: cursor.ch - match[0].length },
        end: cursor,
        query: match[1],
      };
    }
    return null;
  }

  getSuggestions(context: EditorSuggestContext): string[] {
    const query = context.query.toLowerCase();
    return ["tag1", "tag2", "tag3"].filter((t) =>
      t.toLowerCase().includes(query)
    );
  }

  renderSuggestion(value: string, el: HTMLElement): void {
    el.createEl("div", { text: value });
  }

  selectSuggestion(value: string): void {
    if (this.context) {
      const { editor, start, end } = this.context;
      editor.replaceRange(`#${value} `, start, end);
    }
  }
}

// Register in onload():
this.registerEditorSuggest(new TagSuggest(this));
```

## Custom Views

```typescript
import { ItemView, WorkspaceLeaf } from "obsidian";

const VIEW_TYPE = "my-view";

class MyView extends ItemView {
  constructor(leaf: WorkspaceLeaf) {
    super(leaf);
  }

  getViewType(): string {
    return VIEW_TYPE;
  }

  getDisplayText(): string {
    return "My View";
  }

  async onOpen() {
    const container = this.containerEl.children[1];
    container.empty();
    container.createEl("h4", { text: "My custom view" });
  }

  async onClose() {}
}

// Register in onload():
this.registerView(VIEW_TYPE, (leaf) => new MyView(leaf));

// Activate the view:
async activateView() {
  const { workspace } = this.app;
  let leaf = workspace.getLeavesOfType(VIEW_TYPE)[0];
  if (!leaf) {
    const rightLeaf = workspace.getRightLeaf(false);
    if (rightLeaf) {
      await rightLeaf.setViewState({ type: VIEW_TYPE, active: true });
      leaf = rightLeaf;
    }
  }
  if (leaf) workspace.revealLeaf(leaf);
}
```

**Important:** Don't store references to custom views. Use `getLeavesOfType()` to find them.

## Data & Settings

```typescript
// Load persisted data from data.json
const data = await this.loadData();

// Save data to data.json
await this.saveData({ key: "value" });

// Common pattern: merge defaults with saved data
async loadSettings() {
  this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
}

async saveSettings() {
  await this.saveData(this.settings);
}
```

## File Operations

Use `Editor` API for edits to the active note. Use `Vault.process()` for background file modifications (atomic read-modify-write). Use `FileManager.processFrontMatter()` for YAML changes. Use `vault.getFileByPath()` instead of iterating all files. Always `normalizePath()` user-provided paths.

```typescript
const { vault } = this.app;

// Read a file
const file = vault.getFileByPath("path/to/file.md");
if (file) {
  const content = await vault.read(file);

  // Modify a file atomically (read-modify-write in one operation)
  await vault.process(file, (data) => {
    return data.replace("old", "new");
  });

  // Modify frontmatter
  await this.app.fileManager.processFrontMatter(file, (frontmatter) => {
    frontmatter.tags = ["tag1", "tag2"];
  });
}

// Create a file
await vault.create("path/to/new.md", "# Content");

// Normalize user-provided paths
import { normalizePath } from "obsidian";
const safePath = normalizePath(userInput);
```

**Avoid:** Don't use `vault.read()` + `vault.modify()` separately — this is not atomic and the file may change between the two calls. Use `vault.process()` instead.

## Metadata Cache

Access file metadata (frontmatter, tags, links, headings) without reading file contents. Use `metadataCache` for fast lookups instead of parsing files manually.

```typescript
const { metadataCache, vault } = this.app;

// Get cached metadata for a file
const file = vault.getFileByPath("path/to/file.md");
if (file) {
  const cache = metadataCache.getFileCache(file);
  if (cache) {
    const tags = cache.frontmatter?.tags;
    const allTags = cache.tags?.map((t) => t.tag);
    const headings = cache.headings?.map((h) => h.heading);
    const links = cache.links?.map((l) => l.link);
  }
}

// Resolve link targets
const resolvedLinks = metadataCache.resolvedLinks;
// resolvedLinks["path/to/source.md"]["path/to/target.md"] = count

// Wait for metadata cache to be fully resolved after startup
metadataCache.on("resolved", () => {
  // Cache is fully populated — safe to query
});

// Listen for metadata changes
this.registerEvent(
  metadataCache.on("changed", (file, data, cache) => {
    // file was modified and its cache was updated
  })
);
```

## Event System

Register events in `onload()` — they are automatically cleaned up on plugin unload. For the full event reference including all vault, workspace, editor, and metadata events, see `references/events.md`.

### Key Events

```typescript
// File changes
this.registerEvent(this.app.vault.on("create", (file) => { /* ... */ }));
this.registerEvent(this.app.vault.on("modify", (file) => { /* ... */ }));
this.registerEvent(this.app.vault.on("delete", (file) => { /* ... */ }));
this.registerEvent(this.app.vault.on("rename", (file, oldPath) => { /* ... */ }));

// Navigation
this.registerEvent(this.app.workspace.on("file-open", (file) => { /* ... */ }));
this.registerEvent(this.app.workspace.on("active-leaf-change", (leaf) => { /* ... */ }));

// Context menus (see Context Menus section above)
this.registerEvent(this.app.workspace.on("file-menu", (menu, file) => { /* ... */ }));
this.registerEvent(this.app.workspace.on("editor-menu", (menu, editor, view) => { /* ... */ }));

// Editor interception
this.registerEvent(this.app.workspace.on("editor-change", (editor, info) => { /* ... */ }));
this.registerEvent(this.app.workspace.on("editor-paste", (evt, editor, view) => { /* ... */ }));
this.registerEvent(this.app.workspace.on("editor-drop", (evt, editor, view) => { /* ... */ }));

// Startup readiness
this.app.workspace.onLayoutReady(() => { /* workspace is ready */ });
```

### Debouncing

Use `debounce` from Obsidian for frequently firing events like `modify`.

```typescript
import { debounce } from "obsidian";

const debouncedSave = debounce(
  (file: TFile) => { /* process file change */ },
  500,
  true
);

this.registerEvent(this.app.vault.on("modify", debouncedSave));
```

### DOM Events and Intervals

```typescript
// DOM events (auto-cleaned on unload)
this.registerDomEvent(document, "click", (evt: MouseEvent) => { /* ... */ });

// Intervals (auto-cleaned on unload)
this.registerInterval(window.setInterval(() => { /* ... */ }, 5 * 60 * 1000));
```

## Markdown Post-Processing

```typescript
// Modify rendered markdown in reading mode
this.registerMarkdownPostProcessor((element, context) => {
  const codeblocks = element.findAll("code");
  for (const codeblock of codeblocks) {
    const text = codeblock.innerText.trim();
    // Transform content
  }
});

// Handle custom code blocks
this.registerMarkdownCodeBlockProcessor("my-lang", (source, el, ctx) => {
  el.createEl("pre", { text: source.toUpperCase() });
});
```

## Editor Extensions (CodeMirror 6)

```typescript
import { EditorView, ViewPlugin, ViewUpdate } from "@codemirror/view";

const myPlugin = ViewPlugin.fromClass(
  class {
    constructor(view: EditorView) {}
    update(update: ViewUpdate) {}
    destroy() {}
  }
);

// Register in onload():
this.registerEditorExtension([myPlugin]);
```

## Protocol Handlers

```typescript
// Handle obsidian://my-action?param=value URLs
this.registerObsidianProtocolHandler("my-action", (params) => {
  new Notice(`Received: ${JSON.stringify(params)}`);
});
```

## Styling

Use Obsidian's CSS variables so plugins adapt to any theme. Add a `styles.css` file to your plugin root — it loads automatically. For the full CSS variables reference, see `references/styling.md`.

```css
/* styles.css */
.my-plugin-panel {
  background-color: var(--background-secondary);
  border: 1px solid var(--background-modifier-border);
  border-radius: var(--radius-m);
  padding: var(--size-4-3);
  color: var(--text-normal);
}

.my-plugin-muted {
  color: var(--text-muted);
}
```

**Rules:**
- Use CSS classes, not inline styles
- Use CSS variables, not hardcoded colors
- Prefix class names with your plugin ID to avoid conflicts
- Include `styles.css` in GitHub release assets

## Security Rules

- **Never** use `innerHTML`, `outerHTML`, or `insertAdjacentHTML` with user input
- Build DOM elements with `createEl()`, `createDiv()`, `createSpan()`
- Sanitize all external data before rendering

## Mobile Compatibility

To support mobile:
- Avoid Node.js built-in modules (`fs`, `path`, `child_process`)
- Avoid Electron APIs (`remote`, `shell`, `dialog`)
- Don't use regex lookbehind assertions
- Set `isDesktopOnly: false` in manifest.json
- Test on both iOS and Android

## Common Patterns

### Access Active Editor

```typescript
const view = this.app.workspace.getActiveViewOfType(MarkdownView);
if (view) {
  const editor = view.editor;
  const cursor = editor.getCursor();
  const selection = editor.getSelection();
}
```

### Workspace Navigation

```typescript
const view = this.app.workspace.getActiveViewOfType(MarkdownView);
const leaves = this.app.workspace.getLeavesOfType("my-view");
this.app.workspace.iterateAllLeaves((leaf) => { /* ... */ });
```

### Create DOM Safely

```typescript
const container = containerEl.createDiv({ cls: "my-plugin-container" });
container.createEl("h3", { text: "Title" });
container.createEl("p", { text: userInput }); // Safe - text content, not HTML
```
