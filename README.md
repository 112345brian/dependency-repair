# dep-heal

Install the dependencies an editable install is missing, under an explicit policy.

An editable install (`pipx install --editable .`, `pip install -e .`) runs your checkout's code but keeps the
dependency set it had on the day it was installed. Add a dependency to `pyproject.toml`, pull, and every command
dies with `ModuleNotFoundError` until someone reinstalls. `dep-heal` reads the dependencies the checkout declares,
compares them with what the running environment has, and acts on a policy:

| policy | when something is missing |
|---|---|
| `auto` | installs it and says what it installed and where |
| `prompt` | shows the list and the target environment and asks `[y/N]`; with no terminal it installs nothing |
| `off` | reports the list and the manual command; installs nothing |

It checks the *checkout's* `pyproject.toml`, not the installed metadata, because an editable install's metadata is the
thing that is stale. It does nothing for a non-editable install, whose metadata cannot drift from itself.

```python
from dep_heal.api import heal_editable_install
from dep_heal.domain import HealPolicy

result = heal_editable_install(
    "my-dist",
    policy=HealPolicy.PROMPT,
    run_command=my_command_runner,          # argv -> exit code (or None); you decide how processes start
    manual_command='pipx install --editable --force "/path/to/checkout"',
)
if not result.satisfied:
    ...
```

`dep_heal.adapters.stdlib_runner.run_with_subprocess` is a ready-made `run_command` for programs with no process layer
of their own.

## Architecture

Enforced by [archlint](https://github.com/112345brian/archlint) (`archlint check`); rings, innermost first:

| ring | modules | holds |
|---|---|---|
| domain | `domain` | policy, outcomes, results, the "is this requirement met?" rules (pure) |
| ports | `ports` | `RequirementSource`, `Environment`, `Installer`, `Console`, `CommandRunner` |
| application | `heal` | the use case, over the ports |
| adapters | `adapters/*`, `testing` | pyproject / editable-install source, `importlib.metadata` environment, pip installer, terminal console; in-memory fakes |
| composition | `api` | wires the real adapters |

The package never starts a process itself: `PipInstaller` takes the `CommandRunner` its caller binds. Tests use the
fakes in `dep_heal.testing`.
