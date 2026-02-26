# CSS Variables and Theming

Use Obsidian's CSS variables so plugins automatically adapt to any theme (light or dark). Never hardcode colors — always use variables.

## Plugin Styles

Add a `styles.css` file to your plugin root. It is loaded automatically when the plugin is enabled.

## Common CSS Variables

### Text Colors

```css
color: var(--text-normal);        /* Primary text */
color: var(--text-muted);         /* Secondary/dimmed text */
color: var(--text-faint);         /* Very dimmed text */
color: var(--text-on-accent);     /* Text on accent-colored backgrounds */
color: var(--text-success);       /* Success state */
color: var(--text-warning);       /* Warning state */
color: var(--text-error);         /* Error state */
```

### Background Colors

```css
background-color: var(--background-primary);          /* Main content area */
background-color: var(--background-primary-alt);      /* Alternate content area */
background-color: var(--background-secondary);        /* Sidebars, panels */
background-color: var(--background-secondary-alt);    /* Hover on secondary */
background-color: var(--background-modifier-border);  /* Borders */
background-color: var(--background-modifier-hover);   /* Hover state */
background-color: var(--background-modifier-error);   /* Error background */
background-color: var(--background-modifier-success); /* Success background */
```

### Interactive Colors

```css
color: var(--interactive-normal);  /* Default interactive element */
color: var(--interactive-hover);   /* Hovered interactive element */
color: var(--interactive-accent);  /* Active/selected interactive element */
```

### Sizing and Spacing

```css
padding: var(--size-4-1);   /* 4px */
padding: var(--size-4-2);   /* 8px */
padding: var(--size-4-3);   /* 12px */
padding: var(--size-4-4);   /* 16px */
padding: var(--size-4-6);   /* 24px */
padding: var(--size-4-8);   /* 32px */

border-radius: var(--radius-s);  /* Small radius */
border-radius: var(--radius-m);  /* Medium radius */
border-radius: var(--radius-l);  /* Large radius */
```

### Typography

```css
font-family: var(--font-interface);  /* UI text */
font-family: var(--font-text);       /* Note content */
font-family: var(--font-monospace);  /* Code */

font-size: var(--font-ui-small);     /* Small UI text */
font-size: var(--font-ui-medium);    /* Normal UI text */
font-size: var(--font-ui-large);     /* Large UI text */
```

## Example: Theme-Aware Plugin Panel

```css
/* styles.css */
.my-plugin-container {
  background-color: var(--background-secondary);
  border: 1px solid var(--background-modifier-border);
  border-radius: var(--radius-m);
  padding: var(--size-4-3);
  color: var(--text-normal);
}

.my-plugin-container:hover {
  background-color: var(--background-secondary-alt);
}

.my-plugin-header {
  color: var(--text-normal);
  font-size: var(--font-ui-large);
  margin-bottom: var(--size-4-2);
}

.my-plugin-muted {
  color: var(--text-muted);
  font-size: var(--font-ui-small);
}

.my-plugin-error {
  color: var(--text-error);
  background-color: var(--background-modifier-error);
  padding: var(--size-4-2);
  border-radius: var(--radius-s);
}
```

## Rules

- Use CSS classes, not inline styles
- Use Obsidian's CSS variables, not hardcoded colors
- Prefix all class names with your plugin ID to avoid conflicts (e.g., `.my-plugin-header`)
- Add `styles.css` to your GitHub release assets alongside `main.js` and `manifest.json`
