---
name: development
description: "This skill should be used when the user is working with Textual code, asks about a \"textual widget\", \"textual CSS\", \"textual screen\", \"TUI development\", \"textual events\", \"textual bindings\", \"textual workers\", \"TCSS\", \"textual reactive\", or mentions Textual framework concepts, terminal UI patterns, or Textual app architecture."
---

# Textual Development Reference

Comprehensive reference for building terminal user interfaces with Textual.

## App Class

The `App` is the root of every Textual application.

### Class Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `CSS_PATH` | `str \| list[str]` | Path(s) to external `.tcss` stylesheet(s) |
| `CSS` | `str` | Inline CSS string |
| `TITLE` | `str` | App title (shown in Header) |
| `SUB_TITLE` | `str` | Subtitle (shown in Header) |
| `BINDINGS` | `list[Binding \| tuple]` | Key bindings |
| `SCREENS` | `dict[str, Screen]` | Named screens for install |
| `MODES` | `dict[str, str \| Screen]` | Independent screen stacks |
| `DEFAULT_MODE` | `str` | Starting mode |

### Lifecycle

```python
from textual.app import App, ComposeResult
from textual.widgets import Static

class MyApp(App):
    def compose(self) -> ComposeResult:
        """Create child widgets. Called once on startup."""
        yield Static("Hello, world!")

    def on_mount(self) -> None:
        """Called after widgets are mounted to the DOM."""
        pass

if __name__ == "__main__":
    MyApp().run()
```

### Return Values

Type-hint the App to get a return value from `run()`:

```python
class MyApp(App[str]):
    def action_quit_with_value(self) -> None:
        self.exit("user chose this")

result = MyApp().run()  # result: str | None
```

### Suspend

Temporarily hand control back to the terminal:

```python
with self.suspend():
    # Terminal is restored, run external commands
    os.system("vim file.txt")
```

## Built-in Widgets

### Layout & Structure

| Widget | Description |
|--------|-------------|
| `Header` | App header with title and clock |
| `Footer` | Shows active key bindings |
| `Static` | Render static text/Rich renderables |
| `Label` | Simple text label |
| `Placeholder` | Development placeholder |
| `Rule` | Horizontal or vertical separator |
| `Collapsible` | Expandable/collapsible container |
| `ContentSwitcher` | Toggle between child widgets |
| `TabbedContent` | Tab-based content panels |
| `Tabs` | Tab navigation headers |

### Input

| Widget | Description |
|--------|-------------|
| `Input` | Single-line text input |
| `TextArea` | Multi-line text editor with syntax highlighting |
| `MaskedInput` | Input with format mask |
| `Button` | Clickable button |
| `Checkbox` | Boolean toggle |
| `Switch` | Toggle switch |
| `RadioButton` | Mutually exclusive option |
| `RadioSet` | Group of radio buttons |
| `Select` | Dropdown selection |
| `SelectionList` | Multi-select list with checkboxes |

### Data Display

| Widget | Description |
|--------|-------------|
| `DataTable` | Tabular data with sorting/scrolling |
| `ListView` | Scrollable list of items |
| `ListItem` | Item within a ListView |
| `OptionList` | Selectable options list |
| `Tree` | Hierarchical tree view |
| `DirectoryTree` | File system tree |
| `Digits` | Large numeric display |
| `Sparkline` | Compact data visualization |

### Output & Feedback

| Widget | Description |
|--------|-------------|
| `Log` | Scrolling text log |
| `RichLog` | Log with Rich formatting |
| `Markdown` | Render markdown content |
| `MarkdownViewer` | Markdown with table of contents |
| `Pretty` | Pretty-print data structures |
| `LoadingIndicator` | Animated loading spinner |
| `ProgressBar` | Visual progress bar |
| `Toast` | Temporary notification popup |

### Other

| Widget | Description |
|--------|-------------|
| `Link` | Clickable hyperlink |

## Custom Widgets

### compose vs render

Use `compose()` to combine existing widgets:

```python
from textual.widget import Widget
from textual.widgets import Static, Button

class MyPanel(Widget):
    def compose(self) -> ComposeResult:
        yield Static("Panel content")
        yield Button("Action")
```

Use `render()` for a single Rich renderable:

```python
from textual.widget import Widget

class Greeting(Widget):
    def render(self) -> str:
        return "Hello, world!"
```

### Reactive Attributes

Reactive attributes trigger updates when changed:

```python
from textual.reactive import reactive
from textual.widget import Widget

class Counter(Widget):
    count: reactive[int] = reactive(0)

    def render(self) -> str:
        return f"Count: {self.count}"

    def watch_count(self, value: int) -> None:
        """Called when count changes."""
        self.log(f"Count is now {value}")

    def validate_count(self, value: int) -> int:
        """Validate before setting."""
        return max(0, value)
```

Options: `reactive(default, layout=False, recompose=False, always_update=False, init=True)`

- `layout=True` — triggers layout recalculation
- `recompose=True` — re-runs `compose()` on change
- `init=True` — runs watcher on initialization

## TCSS (Textual CSS)

### Selectors

| Selector | Syntax | Example |
|----------|--------|---------|
| Type | `WidgetName` | `Button { color: green; }` |
| ID | `#id` | `#sidebar { width: 30; }` |
| Class | `.class` | `.error { color: red; }` |
| Universal | `*` | `* { padding: 1; }` |
| Descendant | `A B` | `#dialog Button { ... }` |
| Child | `A > B` | `#sidebar > Button { ... }` |

### Pseudo-classes

| Pseudo-class | Matches |
|-------------|---------|
| `:focus` | Widget has focus |
| `:blur` | Widget does not have focus |
| `:hover` | Mouse is over widget |
| `:disabled` | Widget is disabled |
| `:enabled` | Widget is enabled |
| `:dark` | Dark mode active |
| `:light` | Light mode active |
| `:first-child` | First child of parent |
| `:last-child` | Last child of parent |
| `:even` | Even-numbered child |
| `:odd` | Odd-numbered child |
| `:empty` | Widget has no children |
| `:focus-within` | Widget or descendant has focus |

### Key Properties

```tcss
/* Layout */
layout: horizontal | vertical | grid;
dock: top | bottom | left | right;
display: block | none;
overflow-x: auto | hidden | scroll;
overflow-y: auto | hidden | scroll;

/* Sizing */
width: 50 | 50% | auto | 1fr;
height: 10 | 50% | auto | 1fr;
min-width: 20;
max-width: 100;

/* Spacing */
padding: 1 2;
margin: 1 2;

/* Appearance */
background: $surface;
color: $text;
border: solid green;
border-title-color: $accent;
text-style: bold italic underline;
opacity: 0.5;

/* Grid */
grid-size: 3 2;        /* columns rows */
grid-columns: 1fr 2fr;
grid-rows: auto 1fr;
grid-gutter: 1;
column-span: 2;
row-span: 2;

/* Scrollbar */
scrollbar-color: $primary;
scrollbar-size-vertical: 2;
```

### Variables

```tcss
$accent: #1abc9c;
$bg: $surface;

Screen {
    background: $bg;
}

Button {
    color: $accent;
}
```

### Nesting

```tcss
#sidebar {
    width: 30;

    Button {
        width: 100%;
    }

    &:focus {
        border: solid $accent;
    }
}
```

## Screens

### Push / Pop / Switch

```python
# Push a new screen onto the stack
self.app.push_screen(MyScreen())

# Pop the current screen
self.app.pop_screen()

# Replace the current screen
self.app.switch_screen(MyScreen())
```

### Modal Screens

Block interaction with underlying screens:

```python
from textual.screen import ModalScreen
from textual.widgets import Label, Button
from textual.containers import Horizontal

class ConfirmDialog(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        yield Label("Are you sure?")
        yield Horizontal(
            Button("Yes", id="yes", variant="primary"),
            Button("No", id="no"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")
```

### Dismiss with Callback

```python
def handle_result(confirmed: bool | None) -> None:
    if confirmed:
        self.exit()

self.push_screen(ConfirmDialog(), handle_result)
```

### Dismiss with Await

```python
@work
async def confirm_exit(self) -> None:
    confirmed = await self.push_screen_wait(ConfirmDialog())
    if confirmed:
        self.exit()
```

### Modes

Independent screen stacks for app sections:

```python
class MyApp(App):
    MODES = {
        "main": "main_screen",
        "settings": "settings_screen",
    }
    SCREENS = {
        "main_screen": MainScreen,
        "settings_screen": SettingsScreen,
    }
    DEFAULT_MODE = "main"

    BINDINGS = [("m", "switch_mode('main')", "Main"),
                ("s", "switch_mode('settings')", "Settings")]
```

## Events & Messages

### Handler Naming

Message class names map to handler methods:

| Message | Handler |
|---------|---------|
| `Button.Pressed` | `on_button_pressed` |
| `Input.Changed` | `on_input_changed` |
| `Mount` | `on_mount` |
| `Key` | `on_key` |

### The @on Decorator

Target specific widgets with CSS selectors:

```python
from textual.on import on

class MyApp(App):
    @on(Button.Pressed, "#save")
    def save_clicked(self) -> None:
        """Only fires for button with id='save'."""
        self.save()

    @on(Button.Pressed, "#cancel")
    def cancel_clicked(self) -> None:
        self.exit()
```

### Custom Messages

```python
from textual.message import Message

class ColorPicker(Widget):
    class Selected(Message):
        def __init__(self, color: str) -> None:
            self.color = color
            super().__init__()

    def pick(self, color: str) -> None:
        self.post_message(self.Selected(color))

# Parent handles: on_color_picker_selected
```

### Controlling Propagation

```python
def on_button_pressed(self, event: Button.Pressed) -> None:
    event.stop()              # Stop bubbling
    event.prevent_default()   # Prevent default behavior
```

## Key Bindings

### BINDINGS

```python
from textual.binding import Binding

class MyApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),                        # Tuple shorthand
        Binding("d", "toggle_dark", "Dark mode"),     # Binding object
        Binding("ctrl+s", "save", "Save", priority=True),  # Priority binding
    ]

    def action_toggle_dark(self) -> None:
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )

    def action_save(self) -> None:
        self.save_data()
```

`priority=True` — binding works even when a focused widget would normally capture the key.

## Workers

### Async Workers

```python
from textual.worker import Worker, get_current_worker
from textual import work

class MyApp(App):
    @work(exclusive=True)
    async def fetch_data(self, url: str) -> None:
        response = await httpx.AsyncClient().get(url)
        self.query_one("#result", Static).update(response.text)
```

`exclusive=True` cancels any previous worker from the same method before starting.

### Thread Workers

For blocking/synchronous APIs:

```python
@work(exclusive=True, thread=True)
def fetch_data(self, url: str) -> None:
    worker = get_current_worker()
    response = requests.get(url)
    if not worker.is_cancelled:
        self.call_from_thread(self.query_one("#result").update, response.text)
```

**Critical:** Never call UI methods directly from a thread worker. Use `self.call_from_thread()`.

### Worker Groups

```python
@work(group="network")
async def fetch(self, url: str) -> None:
    ...

# Cancel all workers in a group
self.workers.cancel_group(self, "network")
```

## Queries

### Finding Widgets

```python
# Find one widget by type
button = self.query_one(Button)

# Find one by ID
sidebar = self.query_one("#sidebar")

# Find one by ID with type check
sidebar = self.query_one("#sidebar", Static)

# Find all matching
buttons = self.query(Button)
errors = self.query(".error")

# Iterate results
for button in self.query(Button):
    button.disabled = True
```

### Query Methods

```python
results = self.query(".item")

results.first()          # First match
results.last()           # Last match
results.filter(".active")  # Sub-filter

# Bulk operations
results.add_class("hidden")
results.remove_class("hidden")
results.set(disabled=True)
```

## Common Patterns

### Reactive UI Updates

```python
class Dashboard(App):
    count: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static(id="display")
        yield Button("+1", id="increment")

    def watch_count(self, value: int) -> None:
        self.query_one("#display", Static).update(f"Count: {value}")

    @on(Button.Pressed, "#increment")
    def increment(self) -> None:
        self.count += 1
```

### DataTable

```python
from textual.widgets import DataTable

class TableApp(App):
    def compose(self) -> ComposeResult:
        yield DataTable()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Name", "Age", "City")
        table.add_rows([
            ("Alice", 30, "NYC"),
            ("Bob", 25, "LA"),
        ])

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.notify(f"Selected row {event.cursor_row}")
```

### Form Input

```python
from textual.widgets import Input, Button, Static
from textual.containers import Vertical

class FormApp(App):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Input(placeholder="Name", id="name"),
            Input(placeholder="Email", id="email"),
            Button("Submit", id="submit"),
            Static(id="result"),
        )

    @on(Button.Pressed, "#submit")
    def submit_form(self) -> None:
        name = self.query_one("#name", Input).value
        email = self.query_one("#email", Input).value
        self.query_one("#result", Static).update(f"Hi {name} ({email})")
```

### Timers

```python
def on_mount(self) -> None:
    self.set_interval(1.0, self.tick)

def tick(self) -> None:
    self.query_one("#clock", Static).update(str(datetime.now()))
```

### Notifications

```python
self.notify("Operation completed!", title="Success", severity="information")
self.notify("Something went wrong!", severity="error", timeout=10)
```

Severity values: `"information"`, `"warning"`, `"error"`.
