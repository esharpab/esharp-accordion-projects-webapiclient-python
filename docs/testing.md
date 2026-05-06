# Testing

The test suite uses [pytest](https://docs.pytest.org/) and is split into **unit tests** (no hardware required) and **integration tests** (require a live AccordionQ2 device).

## Setup

```bash
# Install with test dependencies
pip install -e ".[dev]"
```

## Unit Tests

Unit tests run entirely offline using mocks. No hardware or network connection is needed.

```bash
pytest tests/unit/ -v
```

Expected output: all tests pass in under a second.

## Integration Tests

Integration tests require a live AccordionQ2 device on the network. The `ACCORDIONQ2_API_URL`
environment variable **must** be set — there is no default:

```bash
# Run all integration tests against a specific device
ACCORDIONQ2_API_URL=http://mydevice.local:5000 pytest tests/ -m integration -v
```

On Windows (PowerShell):

```powershell
$env:ACCORDIONQ2_API_URL = "http://mydevice.local:5000"
pytest tests/ -m integration -v
```

If `ACCORDIONQ2_API_URL` is not set, integration tests are skipped automatically.

### Performance Tests

```bash
ACCORDIONQ2_API_URL=http://mydevice.local:5000 pytest tests/ -m performance -v
```

## Test Markers

| Marker | Description |
|--------|-------------|
| `integration` | Requires a live AccordionQ2 device |
| `performance` | Performance/benchmarking tests |

Tests without a marker are plain unit tests and run by default.

## Hardware-Specific Tests

Some integration tests are automatically **skipped** when the connected hardware does not have the
required modules or channels (e.g. ADC channels, LED tower). No manual configuration is needed —
the test suite adapts to the target device at runtime.

## Continuous Integration

The CI pipeline (`.github/workflows/ci.yml`) runs automatically on every push and pull request:

| Job | Description |
|-----|-------------|
| `lint` | Runs `ruff check` and `ruff format --check` |
| `typecheck` | Runs `mypy --strict` on the `accordionq2` package |
| `test` | Runs unit tests on Ubuntu, Windows, and macOS × Python 3.11, 3.12, 3.13 |

Integration tests are **not** run in CI (no hardware available).

## Pre-commit Hooks

Pre-commit hooks run ruff and mypy automatically before each commit:

```bash
# Install hooks (one-time setup)
pre-commit install

# Run manually against all files
pre-commit run --all-files
```
