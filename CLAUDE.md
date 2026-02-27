# jackery-ha

Home Assistant custom integration for Jackery power stations, distributed via HACS.

## Code Style

- Use typings throughout; code must pass mypy and ruff
- Use `list[]`, `dict[]` rather than `List[]`, `Dict[]`
- Avoid `any` unless absolutely necessary
- Include docstrings in every public-facing method (not required in tests)

## Running Commands

- Always use `uv run` to ensure the virtualenv is used
- Examples: `uv run pytest`, `uv run mypy .`, `uv run ruff check .`

## Dependencies

- Add dependencies using `uv add <package>` (use `--dev` for dev dependencies)

## Project Layout

This is a Home Assistant custom integration, NOT a standard Python package.

- Integration code: `custom_components/jackery/`
- Tests: `tests/`
- HA discovers integrations by `domain` (the directory name under `custom_components/`)
- The `manifest.json` inside `custom_components/jackery/` declares dependencies that HA installs at runtime
- `pyproject.toml` is for dev tooling only (linting, testing, type checking)

## Key Dependency

- `socketry>=0.1.1` — the PyPI library that handles all Jackery API communication (HTTP + MQTT)
- The integration is a thin HA wrapper around socketry's `Client`, `Device`, and `Subscription` classes
- All protocol logic lives in socketry — the integration should NEVER make direct HTTP/MQTT calls

## Home Assistant Patterns

- Use `DataUpdateCoordinator` for data management
- Use `CoordinatorEntity` as the base for all entity classes
- Use frozen dataclass entity descriptions for declarative entity definitions
- Use `ConfigEntryNotReady` for transient setup failures (automatic retry with backoff)
- Use `ConfigEntryAuthFailed` for auth failures (triggers reauth flow)
- Use `entry.runtime_data` (not `hass.data[DOMAIN]`) for storing coordinator
- IoT class: `cloud_push` (MQTT push primary, HTTP poll fallback)

## Testing

- Mock `socketry.Client` in all tests — never hit real APIs
- Use `pytest-homeassistant-custom-component` if available, otherwise mock HA internals
- `pytest-asyncio` with `asyncio_mode = "auto"`
- Aim for 90%+ coverage; don't do excessive work to cover edge cases that provide little value

### Live HA Testing (hot-deploy without releasing)

If the user provides a live HA instance accessible via SSH running this integration, you may debug it directly.

Workflow:
1. `docker ps` to identify the HA container name and `docker inspect <container>` to find the config volume mount path
2. `sudo cp` changed files into `<config_volume>/custom_components/jackery/` (create subdirs as needed)
3. `docker restart <container>` to apply changes
4. Verify in the HA UI — no HACS release needed

## Git Commits

- Use conventional commits: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

## Code Reviews

Conduct **adversarial code reviews** unless otherwise specified:
- Assume the code under review is in the last git commit
- Focus on bugs, edge cases, security issues, and design flaws
- Organize findings by severity (Critical, Moderate, Minor) w/unique numbering
- Include file paths and line numbers for each issue

## Implementation Planning

Use `docs/plan.md` for multi-phase implementation work.

### When Implementing a Phase
1. Read `docs/plan.md` to understand the current phase
2. Implement according to the deliverables and acceptance criteria
3. Run all checks (ruff, mypy, pytest with coverage)
4. Once passing: mark phase complete in plan.md, update README.md, commit

### Continuing Work
Read `docs/plan.md`, check git status/log, continue from where previous session left off.

## Coverage Badge

When coverage changes, update the badge in README.md:
- 90%+ → `brightgreen`, 80-89% → `green`, 70-79% → `yellowgreen`
- 60-69% → `yellow`, 50-59% → `orange`, <50% → `red`

Format: `![Coverage](https://img.shields.io/badge/coverage-XX%25-COLOR)`
