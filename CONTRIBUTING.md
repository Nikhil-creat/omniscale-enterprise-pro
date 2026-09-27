# Contributing to OmniScale Enterprise Pro

Thanks for considering a contribution. This project follows a lightweight,
standard workflow.

## Development setup

See [README.md § Local development](README.md#local-development).

Install the pre-commit hooks once, so lint/format issues are caught before
they hit CI:

```bash
pip install -r requirements-dev.txt
pre-commit install
```

## Workflow

1. Fork the repo and create a branch off `main`: `git checkout -b feature/short-description`
2. Make your change, with tests for new behavior
3. Run the full check locally before pushing:
   ```bash
   ruff check backend tests
   pytest --cov=backend
   ```
4. Open a pull request — the PR template will prompt for what's needed

## Commit messages

Use plain, present-tense descriptions of what the commit does:
`Add rate limit for CNN endpoint`, not `Added` or `Adds`.

## Code style

- Python: formatted/linted with `ruff` (config in `pyproject.toml` if present, else defaults)
- Type hints required on new public functions
- No bare `except:` — catch specific exceptions or `Exception` with a comment why

## Reporting bugs / requesting features

Use the issue templates under **Issues → New Issue** — they ask for the
context maintainers actually need (repro steps, environment, expected vs.
actual behavior).

## Security issues

Do not open a public issue — see [SECURITY.md](SECURITY.md).
