# Testing

The test suite uses [pytest](https://docs.pytest.org/) and talks to a live AccordionQ2 device.

## Setup

```bash
# Install with test dependencies
pip install -e ".[dev]"
```

## Running Tests

### Integration Tests

Integration tests require a live AccordionQ2 device on the network. The `ACCORDIONQ2_API_URL`
environment variable **must** be set — there is no default:

```bash
# Run all tests against a specific device
ACCORDIONQ2_API_URL=http://mydevice.local:5000 pytest tests/ -v
```

On Windows (PowerShell):

```powershell
$env:ACCORDIONQ2_API_URL = "http://mydevice.local:5000"
pytest tests/ -v
```

If `ACCORDIONQ2_API_URL` is not set, pytest will exit immediately with an error.

### Performance Tests

```bash
ACCORDIONQ2_API_URL=http://mydevice.local:5000 pytest tests/ -m performance -v
```

## Test Markers

| Marker | Description |
|--------|-------------|
| `integration` | Requires a live AccordionQ2 device |
| `performance` | Performance/benchmarking tests |

## Hardware-Specific Tests

Some tests are automatically **skipped** when the connected hardware does not have the required
modules or channels (e.g. ADC channels, LED tower). No manual configuration is needed — the
test suite adapts to the target device at runtime.

## Using the Publish Script

The included PowerShell publish script can also run tests:

```powershell
# Run tests (integration + unit)
.\publish-python-package.ps1 -Action Test

# Full pipeline: setup, test, build
.\publish-python-package.ps1 -Action All
```
