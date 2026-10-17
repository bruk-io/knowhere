---
paths:
  - "**/*.py"
  - "**/pyproject.toml"
mode: owner
---
# Python

Applies when reading or writing Python in a repository I own.

Every construct below declares something to the reader, and the declaration
must be true. A tag such as (3.15) is the minimum Python the construct needs, so check
the project's `requires-python`. The `philosophy:python-idioms` skill holds the full
dictionary, including the forms to use on earlier versions.

## Floor and tools

- Python 3.15 is the floor for my own projects, including before it reaches final.
- uv is the only way to run Python, install packages, and manage environments.
  Single-file scripts declare their dependencies inline (PEP 723) and run with `uv run`.
- ruff formats and lints, with DOC501 and DOC502 on. Both need ruff's preview mode, and
  without it ruff ignores them.
- mypy runs in strict mode behind a single `typecheck` command, gated in CI. It does not
  run on every edit.
- pypeeker enforces the import boundaries declared in `[tool.pypeeker]`. Run
  `pypeeker check --strict`, because plain `check` hides the heuristic findings.
- pytest runs against a `src/` layout.
- A multi-package repository is a uv workspace: the root is not a package, there is one
  lock and one venv, and shared config lives at the root. pytest then needs
  `--import-mode=importlib` together with `consider_namespace_packages = true`, and
  strict mypy needs `explicit_package_bases` with a `mypy_path` that lists every
  member's `src/`.

## Core and shell

- Functional core, imperative shell. The logic takes data and returns data. Reading
  files, calling networks, and writing databases happen at the edges, and the import
  contract keeps them out of the core.
- Pure core, thin shell at the size of a function: the logic takes plain data and hands
  back what should happen next as a value, and one thin function on the outside does
  the I/O and acts on it. That outer function is the only thing that touches the
  network, the database, or the clock.
- Determinism enters the core as data, through parameters such as `now` and `rng`. It
  never enters by patching.

A retry loop written this way. `next_step` and `backoff_s` are all the logic, and
neither one can do I/O. `send_with_retry` is the only thing that touches the network,
the token, or the clock.

```python
class Step(Enum):
    DONE = auto()
    REFRESH_AUTH = auto()
    RETRY = auto()
    FAIL = auto()


def next_step(status: int, attempt: int) -> Step:
    if 200 <= status < 300:
        return Step.DONE
    if status == 401 and attempt == 1:
        return Step.REFRESH_AUTH
    if status >= 500 and attempt < 3:
        return Step.RETRY
    return Step.FAIL


def backoff_s(attempt: int) -> float:
    return 0.2 * 2.0**attempt


def send_with_retry(request: Request) -> Response:
    """Send a request, refreshing auth once and retrying server errors.

    Raises:
        HttpError: The last response was not a success.
    """
    attempt = 1
    while True:
        response = send(request)
        match next_step(response.status, attempt):
            case Step.DONE:
                return response
            case Step.REFRESH_AUTH:
                refresh_token()
            case Step.RETRY:
                time.sleep(backoff_s(attempt))
            case Step.FAIL:
                raise HttpError(response.status)
            case _ as unreachable:
                assert_never(unreachable)
        attempt += 1
```

The logic is testable from the start, with plain inputs and no mocks, so testing a
branch is one line that passes in two numbers:

```python
assert next_step(503, 1) is Step.RETRY
assert next_step(503, 3) is Step.FAIL
assert next_step(401, 1) is Step.REFRESH_AUTH
assert next_step(401, 2) is Step.FAIL
```

Written the usual way, with the logic and the I/O mixed in one function, testing a
branch means faking the network, the token refresh, and the clock, and changing the
retry rules means editing the same function that makes the calls.

## Classes and names

- The `class` keyword appears in four declared forms and almost nowhere else: dataclass
  for shape, `Protocol` for contracts, Enum for closed sets, and Exception subclasses
  for failure. Behaviour lives in functions.
- A bare class that bundles state with methods is the last resort. Write one only when
  an invariant must hold while the state changes, or a resource has a lifecycle worth
  guarding.
- No inheritance in the code that holds the logic.
- Private by default. A name loses its leading underscore only when a caller exists
  elsewhere.
- `__init__.py` holds imports and `__all__` only. Behaviour lives in named modules.

## Data

- A frozen dataclass is the default record. To change a value, make a copy with the
  change: `dataclasses.replace`, or `copy.replace` (3.13). Use a NamedTuple only when
  positional access is part of the interface.
- The value that says what happens next is an Enum when the steps are a closed set of
  names, or a StrEnum when it crosses the wire. Steps that carry data are a union of
  frozen dataclasses or NamedTuples. The shell matches on it.
- A TypedDict declares a dict that crosses a boundary. Use `closed=True` (3.15) in new
  code.
- `frozendict` (3.15) is the immutable mapping.
- `sentinel` (3.15) creates our own named sentinels: `MISSING = sentinel("MISSING")`,
  compared with `is`. Define one when a state needs a value of its own and None is a
  real value.
- `list` says the data will change and `tuple` says it will not. A comprehension says
  the whole sequence is needed now and a generator says it is not. A full list built
  only to feed a single `sum()` is a small lie.
- `itertools.batched` splits into chunks, and unpacking in a comprehension (3.15),
  `[*chunk for chunk in chunks]`, flattens. Both replace hand-written loops whose
  purpose a reader must work out.

## Control flow and errors

- `match` declares the shape of data and `if` declares a condition. Use `match` on a
  closed set of shapes and end it with `assert_never`, so the type checker fails any
  match that misses a case when the set grows:

  ```python
  match event:
      case Purchase(): ...
      case Refund(): ...
      case _ as unreachable:
          assert_never(unreachable)
  ```

- Match patterns are literals, dotted names, or class patterns. Never a bare name:
  `case pending:` captures whatever arrives into `pending` instead of comparing against
  it.
- Exceptions are for exceptional situations, never for ordinary control flow. Raise
  natively; do not return Result types.
- Every exception a function raises is listed in its docstring.
- At the edges, attach context with `Exception.add_note` so the documented type is the
  type that crosses. `except*` belongs only with TaskGroup code.

## Syntax at the floor

- Generics use the 3.12 syntax, `def first[T](items: Sequence[T]) -> T`, and the `type`
  statement for aliases. `TypeVar` is legacy.
- `from __future__ import annotations` goes away at 3.14.
- An f-string says the text is finished. A t-string (3.14) says it is a template that
  someone must process. A function that accepts a t-string can refuse a plain string by
  type.
- `lazy import` (3.15) belongs at a program's entry points. Confirm the module has no
  side effects at load time before using it.
