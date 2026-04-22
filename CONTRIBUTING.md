# Contributing to monopigi-python

Thanks for your interest in contributing to the Monopigi Python SDK.

## What this repo is

This is the official Python SDK and CLI for the [Monopigi API](https://monopigi.com) — a unified interface to Greek government data (procurement, decisions, energy permits, statistics, and more). The SDK is open source under Apache 2.0. The API itself is a commercial service.

## Ways to contribute

- **Bug reports** — open an issue with a minimal reproduction
- **Documentation fixes** — typos, unclear examples, missing cases
- **New features** — open an issue first to discuss before implementing

## Development setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/monopigi/monopigi-python.git
cd monopigi-python
uv sync --group dev
```

Run tests:

```bash
uv run pytest tests/ -v
```

Run lint:

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

All tests are mocked — no API key is required to run the test suite.

## Pull requests

1. Fork the repo and create a branch from `main`
2. Make your changes with tests where applicable
3. Ensure `pytest` and `ruff check` both pass
4. Open a PR with a clear description of what changed and why

## Commit style

Use [conventional commits](https://www.conventionalcommits.org/):

```
feat: add X
fix: correct Y
docs: update Z
test: cover edge case W
```

## Reporting security issues

Do **not** open a public issue for security vulnerabilities. Email [info@monopigi.com](mailto:info@monopigi.com) instead.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
