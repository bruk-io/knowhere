---
name: app
description: "This skill should be used when the user asks to \"create a textual app\", \"scaffold a TUI\", \"new terminal app\", \"create a terminal UI\", \"textual app scaffold\", or mentions Textual app generation, TUI project setup, or terminal application scaffolding."
---

# Textual App Scaffolding

Generate a Textual TUI application with an App subclass, TCSS stylesheet, optional Header/Footer, and optional example Screen.

## Using the Copier Template

```bash
uvx copier copy --trust --defaults \
  --data app_name="<name>" \
  --data app_class="<ClassName>" \
  --data app_title="<title>" \
  --data include_header=true \
  --data include_footer=true \
  --data include_example_screen=false \
  "${CLAUDE_PLUGIN_ROOT}/skills/app/templates/textual-app/" \
  .
```

### Template Options

- `app_name` (str, default: "app") — Name for the app file (without .py extension)
- `app_class` (str, default: "MyApp") — App subclass name
- `app_title` (str, default: "My Textual App") — Display title shown in the header
- `include_header` (bool, default: true) — Include Header widget
- `include_footer` (bool, default: true) — Include Footer widget
- `include_example_screen` (bool, default: false) — Include an example Screen subclass

### Workflow

1. Infer the app name from context if not provided (e.g. project name, directory name)
2. Determine a sensible `app_class` name from the app name (e.g. "dashboard" -> "DashboardApp")
3. Run the copier template
4. After generation, suggest running the app: `uv run python <app_name>.py`
5. If the user needs additional widgets or screens, guide them using the development skill

## Generated Output

The template produces:

- **`<app_name>.py`** — Main app file with App subclass, compose(), CSS_PATH, BINDINGS, dark mode toggle
- **`<app_name>.tcss`** — Base Textual CSS stylesheet
- **`screens.py`** — (optional) Example Screen subclass with dismiss pattern

## Notes

- The generated app uses PEP 723 inline script metadata so it runs standalone via `uv run python <app_name>.py`
- Textual must be installed (`uv add textual`) if integrating into an existing project
