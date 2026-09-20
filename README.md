# stec

**S**imple, **T**yped, **E**xpressive **C**onfig — a tiny, human-friendly
configuration language for Python applications, with **zero dependencies**.

```stec
var dev = true

expose int port = 8080
expose string secret = "my-secret"
expose string url = $dev ? "127.0.0.1" : "0.0.0.0"
```

```python
from stec import Stec

Stec.load("app.stec")

Stec.port   # 8080
Stec.url    # "127.0.0.1"
```

No YAML indentation traps, no `.env` string coercion — values are typed and
validated when the file is loaded, so bad configuration fails fast at startup
with a clear message and a line/column position.

---

## Why stec?

| Problem with `.env` / plain dicts | How stec helps |
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
pip install stec
```

---

## The language

A stec file is a list of declarations. There are four kinds:
`expose`, `var`, `export env`, and `import env` — the last two integrate
with the process environment (see below).

### `expose` — public, typed values

```stec
expose int port = 8080
expose float ratio = 1.5
expose string name = "my-app"
expose bool debug = false
```

An `expose` declares a value that is published by the `Stec` singleton.
The declared type must match the value:

- `int` — integer literals (`8080`, `0`)
- `float` — decimal literals (`1.5`, `0.25`)
- `string` — double-quoted strings (`"hello"`)
- `bool` — `true` or `false`

Typing is **strict**: `bool` is not accepted where `int` is expected, and
`int` is not accepted where `float` is expected. This keeps errors obvious:

```stec
expose int port = "8080"   # Error: cannot expose string value '8080' as 'int'
expose float ratio = 1     # Error: cannot expose int value 1 as 'float'
```

### `var` — internal variables

```stec
var dev = true
```

A `var` is *not* published. It exists to be referenced by `$name` in later
declarations — ideal for environment switches or derived defaults.

### `$variables` and ternaries

Values can reference previously declared names with `$name`, and any value can
be made conditional with a ternary:

```stec
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

```stec
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

```stec
# runtime switches
var dev = true  # flip for prod

expose int port = 8080
```

### Environment integration

stec can push values out to, and pull values in from, the process environment.

**`export env NAME = value`** sets the OS environment variable `NAME` for the
current process (child processes inherit it):

```stec
export env MYAPP_MODE = $dev ? "development" : "production"
```

- Values are formatted like interpolation: `true`/`false`, `1.5`, `8080`.
- Exported names join the document namespace, so later `$name` and
  `${name}` references can use them.
- Exported values are *not* published on the `Stec` singleton — use
  `expose` for that.

**`import env TYPE NAME = DEFAULT`** reads the environment variable `NAME`,
coerces it to the declared type, and publishes it like `expose`. The default
is optional:

```stec
import env int PORT = 8080        # falls back to 8080 when PORT is not set
import env string MYAPP_TOKEN     # fails at load time when MYAPP_TOKEN is not set
```

- When the variable exists, its raw string is coerced to the type
  (`"9090"` becomes `9090`); a value that cannot be coerced raises
  `StecTypeError` at load time.
- `bool` accepts `true` / `false`, case-insensitively.
- When the variable is missing, the default is evaluated and used; with no
  default, loading fails with `StecNameError`.

### Strings

Strings are double-quoted and support common escape sequences:

```stec
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

`Stec` is a singleton: every module in your application that imports it gets
the **same object**. Load once (typically at startup), read anywhere.

### `app.stec`

```stec
var dev = true

expose int port = 8080
expose string secret = "my-secret"
expose string url = $dev ? "127.0.0.1" : "0.0.0.0"
```

### `main.py`

```python
from stec import Stec

Stec.load("app.stec")

Stec.port            # 8080          (attribute access)
Stec["url"]          # "127.0.0.1"   (item access)
Stec.get("port")     # 8080          (with optional default)
Stec.get("missing")  # None
```

### API reference

| Member | Description |
| --- | --- |
| `Stec.load(path, force=False)` | Parse and evaluate the file into the singleton. Returns the singleton itself (chainable). |
| `Stec.<name>` | Attribute access to an exposed value. |
| `Stec["<name>"]` | Item access to an exposed value. |
| `Stec.get(name, default=None)` | Access with a fallback for missing values. |
| `Stec.as_dict()` | Copy of all exposed values as a plain `dict`. |
| `"name" in Stec` | Check whether a value is exposed. |
| `Stec.is_loaded` | `True` once a file has been loaded. |
| `Stec.loaded_from` | Path the configuration was loaded from, or `None`. |
| `Stec.load(path, force=True)` | Reload, replacing all previous values. |
| `Stec.reset()` | Forget the loaded configuration (useful in tests). |

Notes:

- Loading twice without `force=True` raises `StecAlreadyLoadedError` —
  silent double-loading usually hides a bug, so it is treated as one.
- A failed load leaves the singleton **unloaded**: fix the file and load again.
- Only `expose` and `import env` declarations are published; `var` and
  `export env` values stay internal.
- `repr(Stec)` shows the loaded path and key names, but never values —
  safe to log even if the configuration contains secrets.

```python
Stec.load("app.stec")
print(Stec)   # Stec(loaded_from='app.stec', keys=['port', 'secret', 'url'])
```

---

## Error handling

All errors derive from `StecError`, so catching that single type is enough
for a top-level handler. Errors raised while parsing or evaluating include a
`line`/`column` position, and their messages display it.

```python
from stec import Stec, StecError

try:
    Stec.load("app.stec")
except StecError as error:
    print(error)  # e.g. "cannot expose string value 'abc' as 'int' for 'port' at line 4, column 1"
```

| Exception | Raised when |
| --- | --- |
| `StecError` | Base class for everything stec raises. |
| `StecSyntaxError` | The file cannot be tokenized or parsed. |
| `StecTypeError` | A value does not match the declared type, a ternary condition is not a `bool`, an environment value cannot be coerced, or an `import env` default has the wrong type. |
| `StecNameError` | An undefined reference, a duplicate declaration, or a required environment variable that is not set. |
| `StecLoadError` | The file cannot be read or decoded (missing file, bad UTF-8...). |
| `StecAlreadyLoadedError` | `load()` is called twice without `force=True`. |

```stec
expose int port = 8080
expose int port = 9090
```

```text
StecNameError: duplicate declaration of 'port' at line 2, column 1
```

---

## Quick example

### `app.stec`

```stec
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
from stec import Stec

Stec.load("app.stec")

for key, value in Stec.as_dict().items():
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
git clone https://github.com/<you>/stec.git
cd stec
pip install -e ".[dev]"
pytest
```

### Project layout

```text
src/stec/
├── nodes.py       # AST node dataclasses (Position, Literal, Ternary, ...)
├── parser.py      # hand-written tokenizer + recursive-descent parser
├── evaluator.py   # ordered evaluation and type checking
├── config.py      # the Stec singleton
├── errors.py      # exception hierarchy
└── main.py        # small playground (python src/stec/main.py)

tests/             # pytest suite (parser, evaluator, singleton)
```

The parser is written from scratch (no Lark, no YAML, nothing) so the package
ships with zero runtime dependencies.

---

## Roadmap

- [x] Comments (`#` to end of line)
- [x] String interpolation: `"postgres://localhost:${port}"`
- [ ] Environment overrides (`STEC_PORT` beats `port`)

## License

[MPL-2.0](LICENSE)
