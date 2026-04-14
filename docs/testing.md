# Testing

The test suite uses [pytest](https://docs.pytest.org/) and talks to a live AccordionQ2 device.

## Setup

```bash
# Install with test dependencies
pip install -e ".[dev]"
```

## Running Tests

### Integration Tests

Integration tests require a live AccordionQ2 device on the network:

```bash
# Run all integration tests
pytest tests/ -m integration -v

# Override the default device URL
ACCORDIONQ2_API_URL=http://mydevice:5000 pytest tests/ -m integration
```

The default URL is `http://agent64.local:5000`.

### Performance Tests

```bash
pytest tests/ -m performance -v
```

## Test Markers

| Marker | Description |
|--------|-------------|
| `integration` | Requires a live AccordionQ2 device |
| `performance` | Performance/benchmarking tests |

## Using the Publish Script

The included PowerShell publish script can also run tests:

```powershell
# Run tests (integration + unit)
.\publish-python-package.ps1 -Action Test

# Full pipeline: setup, test, build
.\publish-python-package.ps1 -Action All
```
