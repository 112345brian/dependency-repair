# dependency-repair

Install the dependencies an editable install is missing, under an explicit policy.

An editable install (`pipx install --editable .`, `pip install -e .`) runs your checkout's code but keeps the
dependency set it had on the day it was installed. Add a dependency to `pyproject.toml`, pull, and every command
dies with `ModuleNotFoundError` until someone reinstalls. `dependency-repair` reads the dependencies the checkout declares,
compares them with what the running environment has, and acts on a policy:

| policy | when something is missing |
|---|---|
| `auto` | installs it, after saying every package it is about to install and where |
| `prompt` | shows every package it would install and asks once; with no terminal it installs nothing |
| `off` | reports the list and the manual command; installs nothing |

The list is complete: before installing, it asks `pip install --dry-run --report` what would be added, so the packages
your requirements pull in are named too.

```
This will install 12 packages: Sphinx==9.2.0, alabaster==1.0.0, babel==2.18.0, ... into C:\Users\me\pipx\venvs\my-dist. Continue? [y/N]
```

If pip cannot work the list out (an old pip, no network), the prompt says so rather than pretending it is exact:
`This will install flask>=3 (and anything they depend on) into ...`.

## Choosing what to require

By default only `[project].dependencies` is required. The caller names any optional-dependency groups to require on top
of that with `extras=`; this package has no default group of its own, and the caller's list is the only one it reads. A
group the project does not declare is an error that names it, not a silent skip.

```python
repair_editable_install("my-dist", ..., extras=("tracker",))   # base requirements plus [project.optional-dependencies].tracker
```

It checks the *checkout's* `pyproject.toml`, not the installed metadata, because an editable install's metadata is the
thing that is stale. It does nothing for a non-editable install, whose metadata cannot drift from itself.

```python
from dependency_repair.api import repair_editable_install
from dependency_repair.domain import RepairPolicy

result = repair_editable_install(
    "my-dist",
    policy=RepairPolicy.PROMPT,
    run_command=my_command_runner,          # argv -> exit code (or None); you decide how processes start
    manual_command='pipx install --editable --force "/path/to/checkout"',
)
if not result.satisfied:
    ...
```

`dependency_repair.adapters.stdlib_runner.run_with_subprocess` is a ready-made `run_command` for programs with no process layer
of their own.

## Architecture

Enforced by [archlint](https://github.com/112345brian/archlint) (`archlint check`); rings, innermost first:

| ring | modules | holds |
|---|---|---|
| domain | `domain` | policy, outcomes, results, the "is this requirement met?" rules (pure) |
| ports | `ports` | `RequirementSource`, `Environment`, `Installer`, `Console`, `CommandRunner` |
| application | `repair` | the use case, over the ports |
| adapters | `adapters/*`, `testing` | pyproject / editable-install source, `importlib.metadata` environment, pip installer, terminal console; in-memory fakes |
| composition | `api` | wires the real adapters |

The package never starts a process itself: `PipInstaller` takes the `CommandRunner` its caller binds. Tests use the
fakes in `dependency_repair.testing`.
