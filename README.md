# konfig

Typed, expressive configuration for Python applications — in a tiny, human-friendly
language, with **zero dependencies**.

```konfig
var dev = true

expose int port = 8080
expose string secret = "my-secret"
expose string url = $dev ? "127.0.0.1" : "0.0.0.0"
```

```python
from konfig import Konfig

Konfig.load("app.konfig")

Konfig.port   # 8080
Konfig.url    # "127.0.0.1"
```

No YAML indentation traps, no `.env` string coercion — values are typed and
validated when the file is loaded, so bad configuration fails fast at startup
with a clear message and a line/column position.

---

## Why konfig?

| Problem with `.env` / plain dicts | How konfig helps |
| --- | --- |
| Everything is a string (`PORT="8080"` is a string) | Real types: `int`, `float`, `string`, `bool` |
| Nothing is validated | Type errors raised at load time, with position |
| Repeated values everywhere | `$variables` declared once, reused everywhere |
| Env-dependent values need code | Built-in ternary: `$dev ? "127.0.0.1" : "0.0.0.0"` |
| Values scattered across files | One file, loaded once, readable from everywhere |

And it is just Python — no services, no DSL runtime, no dependencies.

---

## Installation

Requires Python **3.10+**. There are no runtime dependencies.

```bash
pip install konfig
```

---

## The language

A konfig file is a list of declarations. There are two kinds:

### `expose` — public, typed values

```konfig
expose int port = 8080
expose float ratio = 1.5
expose string name = "my-app"
expose bool debug = false
```

An `expose` declares a value that is published by the `Konfig` singleton.
The declared type must match the value:

- `int` — integer literals (`8080`, `0`)
- `float` — decimal literals (`1.5`, `0.25`)
- `string` — double-quoted strings (`"hello"`)
- `bool` — `true` or `false`

Typing is **strict**: `bool` is not accepted where `int` is expected, and
`int` is not accepted where `float` is expected. This keeps errors obvious:

```konfig
expose int port = "8080"   # Error: cannot expose string value '8080' as 'int'
expose float ratio = 1     # Error: cannot expose int value 1 as 'float'
```

### `var` — internal variables

```konfig
var dev = true
```

A `var` is *not* published. It exists to be referenced by `$name` in later
declarations — ideal for environment switches or derived defaults.

### `$variables` and ternaries

Values can reference previously declared names with `$name`, and any value can
be made conditional with a ternary:

```konfig
var dev = true

expose string url = $dev ? "127.0.0.1" : "0.0.0.0"
expose string name = $dev ? "my-app-dev" : "my-app"
```

Rules:

- The condition must be a `bool`.
- Ternaries are lazy: only the branch that is taken is evaluated.
- `$name` must be declared **before** it is used.
- Variables can be chained: `cond ? $a ? 1 : 2 : 3`.

### Interpolation

Strings can embed previously declared names with `${name}` — the value is
rendered into the text:

```konfig
var host = "localhost"

expose int port = 8080
expose string url = "http://${host}:${port}/"
expose string mode = "debug=${debug}"   # bools render as true/false
```

- Any name declared before the string can be interpolated, including
  other `expose` values.
- `${name}` must be declared **before** the string that uses it.
- Bools render as `true`/`false`, numbers render as written (`1.5`).
- To include a literal `${...}` in a string, escape the dollar: `"\${price}"`.

### Comments

`#` starts a comment that runs to the end of the line — it can occupy its own
line or trail a declaration:

```konfig
# runtime switches
var dev = true  # flip for prod

expose int port = 8080
```

### Strings

Strings are double-quoted and support common escape sequences:

```konfig
expose string greeting = "line\nbreak"
expose string quoted  = "she said \"hi\""
expose string unicode = "café \u00e9"
```

| Escape | Meaning |
| --- | --- |
| `\\` | backslash |
| `\"` | double quote |
| `\n` | newline |
| `\t` | tab |
| `\r` | carriage return |
| `\0` | null character |
| `\b` | backspace |
| `\f` | form feed |
| `\$` | dollar sign (prevents `${...}` interpolation) |
| `\uXXXX` | unicode code point (4 hex digits) |

### Names

Names must start with a letter or `_` and may contain letters, digits, and
`_`. `$` followed by a name references a variable. Whitespace (including
newlines) between tokens is ignored.

---

## Using the singleton

`Konfig` is a singleton: every module in your application that imports it gets
the **same object**. Load once (typically at startup), read anywhere.

### `app.konfig`

```konfig
var dev = true

expose int port = 8080
expose string secret = "my-secret"
expose string url = $dev ? "127.0.0.1" : "0.0.0.0"
```

### `main.py`

```python
from konfig import Konfig

Konfig.load("app.konfig")

Konfig.port            # 8080          (attribute access)
Konfig["url"]          # "127.0.0.1"   (item access)
Konfig.get("port")     # 8080          (with optional default)
Konfig.get("missing")  # None
```

### API reference

| Member | Description |
| --- | --- |
| `Konfig.load(path, force=False)` | Parse and evaluate the file into the singleton. Returns the singleton itself (chainable). |
| `Konfig.<name>` | Attribute access to an exposed value. |
| `Konfig["<name>"]` | Item access to an exposed value. |
| `Konfig.get(name, default=None)` | Access with a fallback for missing values. |
| `Konfig.as_dict()` | Copy of all exposed values as a plain `dict`. |
| `"name" in Konfig` | Check whether a value is exposed. |
| `Konfig.is_loaded` | `True` once a file has been loaded. |
| `Konfig.loaded_from` | Path the configuration was loaded from, or `None`. |
| `Konfig.load(path, force=True)` | Reload, replacing all previous values. |
| `Konfig.reset()` | Forget the loaded configuration (useful in tests). |

Notes:

- Loading twice without `force=True` raises `KonfigAlreadyLoadedError` —
  silent double-loading usually hides a bug, so it is treated as one.
- A failed load leaves the singleton **unloaded**: fix the file and load again.
- Only `expose` declarations are published; `var` values stay internal.
- `repr(Konfig)` shows the loaded path and key names, but never values —
  safe to log even if the configuration contains secrets.

```python
Konfig.load("app.konfig")
print(Konfig)   # Konfig(loaded_from='app.konfig', keys=['port', 'secret', 'url'])
```

---

## Error handling

All errors derive from `KonfigError`, so catching that single type is enough
for a top-level handler. Errors raised while parsing or evaluating include a
`line`/`column` position, and their messages display it.

```python
from konfig import Konfig, KonfigError

try:
    Konfig.load("app.konfig")
except KonfigError as error:
    print(error)  # e.g. "cannot expose string value 'abc' as 'int' for 'port' at line 4, column 1"
```

| Exception | Raised when |
| --- | --- |
| `KonfigError` | Base class for everything konfig raises. |
| `KonfigSyntaxError` | The file cannot be tokenized or parsed. |
| `KonfigTypeError` | A value does not match the declared `expose` type, or a ternary condition is not a `bool`. |
| `KonfigNameError` | A `$variable` is undefined or a name is declared twice. |
| `KonfigLoadError` | The file cannot be read or decoded (missing file, bad UTF-8...). |
| `KonfigAlreadyLoadedError` | `load()` is called twice without `force=True`. |

```konfig
expose int port = 8080
expose int port = 9090
```

```text
KonfigNameError: duplicate declaration of 'port' at line 2, column 1
```

---

## Quick example

### `app.konfig`

```konfig
# runtime switches
var dev = true  # flip for prod

expose int port = 8080
expose int pool = 10
expose bool debug = $dev
expose string database_url = $dev
    ? "postgres://localhost:5432/app?pool=${pool}"
    : "postgres://db.internal:5432/app?pool=${pool}"
```

### `main.py`

```python
from konfig import Konfig

Konfig.load("app.konfig")

for key, value in Konfig.as_dict().items():
    print(f"{key} = {value!r}")
```

```text
port = 8080
pool = 10
debug = True
database_url = 'postgres://localhost:5432/app?pool=10'
```

---

## Development

```bash
git clone https://github.com/<you>/konfig.git
cd konfig
pip install -e ".[dev]"
pytest
```

### Project layout

```text
src/konfig/
├── nodes.py       # AST node dataclasses (Position, Literal, Ternary, ...)
├── parser.py      # hand-written tokenizer + recursive-descent parser
├── evaluator.py   # ordered evaluation and type checking
├── config.py      # the Konfig singleton
├── errors.py      # exception hierarchy
└── main.py        # small playground (python src/konfig/main.py)

tests/             # pytest suite (parser, evaluator, singleton)
```

The parser is written from scratch (no Lark, no YAML, nothing) so the package
ships with zero runtime dependencies.

---

## Roadmap

- [x] Comments (`#` to end of line)
- [x] String interpolation: `"postgres://localhost:${port}"`
- [ ] Environment overrides (`KONFIG_PORT` beats `port`)

## License

[MPL-2.0](LICENSE)
