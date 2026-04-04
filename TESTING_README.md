# Running the AccordionQ2 Python Integration Tests

A step-by-step guide for running the Python test suite that mirrors the
C# `WebApiClient.Tests` project.

---

## Prerequisites

| What | Why |
|------|-----|
| **Python 3.8+** | The client library requires Python 3.8 or newer. |
| **pip** | Comes bundled with Python. Used to install dependencies. |
| **Network access to an AccordionQ2 device** | These are *integration* tests — they talk to real hardware over HTTP. |

> **Tip:** Run `python --version` in a terminal to check your Python version.
> On some systems the command is `python3` instead of `python`.

---

## Step 1 — Open a terminal in the right folder

```
cd C:\dev\source\accordionq2\submodules\webapiclient-python
```

---

## Step 2 — Create a virtual environment (recommended)

A virtual environment keeps test dependencies isolated from your system Python.

```bash
# Create the virtual environment (one-time)
python -m venv .venv

# Activate it
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Windows CMD:
.\.venv\Scripts\activate.bat

# Linux / macOS:
source .venv/bin/activate
```

Your prompt should now show `(.venv)` at the beginning.

---

## Step 3 — Install the package and test dependencies

```bash
pip install -e ".[dev]"
```

This installs:
- The `accordionq2` client library (in editable/development mode)
- `pytest` (the test runner)

---

## Step 4 — Run the tests

### Run all integration tests

```bash
pytest tests/ -m integration -v -s
```

| Flag | What it does |
|------|-------------|
| `-m integration` | Only run tests marked as integration tests |
| `-v` | Verbose — show each test name and result |
| `-s` | Show `print()` output (measurements, channel values, etc.) |

### Run performance tests only

```bash
pytest tests/ -m performance -v -s
```

### Run a single test file

```bash
pytest tests/test_connection.py -v -s
```

### Run a single test by name

```bash
pytest tests/test_resources.py -v -s -k "test_get_value_cpu_temp"
```

---

## Step 5 — Targeting a different device

By default the tests connect to `http://agent64.local:5000`.

To use a different device, set the `ACCORDIONQ2_API_URL` environment variable:

```bash
# PowerShell
$env:ACCORDIONQ2_API_URL = "http://192.168.1.42:5000"
pytest tests/ -m integration -v -s

# CMD
set ACCORDIONQ2_API_URL=http://192.168.1.42:5000
pytest tests/ -m integration -v -s

# Linux / macOS
ACCORDIONQ2_API_URL=http://192.168.1.42:5000 pytest tests/ -m integration -v -s
```

---

## What to expect

### If everything works

```
tests/test_connection.py::test_get_status_returns_connected PASSED
tests/test_channels.py::test_get_all_returns_non_empty PASSED
tests/test_channels.py::test_get_all_channels_have_aliases PASSED
tests/test_channels.py::test_get_channel_by_alias_analog PASSED
...
tests/test_resources.py::test_get_values_multiple_resources PASSED

==================== 19 passed in 4.23s ====================
```

Each `PASSED` means the test ran successfully against the live hardware.
The `-s` flag also shows diagnostic output like channel values, module
names, and voltage readings.

### If the device is unreachable

```
FAILED tests/test_connection.py::test_get_status_returns_connected
    ConnectionError: HTTPConnectionPool(host='agent64.local', port=5000):
    Max retries exceeded ...
```

**Fix:** Make sure the device is powered on, on the same network, and that
the URL/port is correct. The default port is **5000**.

### If a test fails with an assertion

```
FAILED tests/test_resources.py::test_get_value_mon_3v3_returns_voltage_in_range
    AssertionError: 3.3V rail at 4.2V seems out of range
```

This means the hardware returned an unexpected value. Check the physical
setup (power supply, cabling, etc.).

### Performance tests

The performance tests print throughput measurements:

```
Roundtrip test: 1000 iterations
  Total time : 12345.6 ms
  Average    : 12.35 ms/request
  Throughput : 81.0 req/s
```

These are informational — the tests always pass as long as the device
responds.

---

## Test-to-C# mapping

| C# Test Class | Python Test File | Tests |
|---------------|-----------------|-------|
| `ConnectionTests` | `test_connection.py` | 1 |
| `ChannelsTests` | `test_channels.py` | 6 |
| `ModulesTests` | `test_modules.py` | 6 |
| `ResourcesTests` | `test_resources.py` | 6 |
| `ApplicationTests` | `test_application.py` | 5 |
| `MediaTests` | `test_media.py` | 1 |
| `PerformanceTests` | `test_performance.py` | 2 |
| **Total** | | **27** |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'accordionq2'` | Run `pip install -e ".[dev]"` from the repo root |
| `pytest: command not found` | Run `pip install pytest` or activate your venv |
| `ConnectionError` / `Timeout` | Check device is reachable: `ping agent64.local` |
| Tests pass but no output | Add `-s` flag to see `print()` output |
| `SKIPPED` on app/license tests | Server-side timeout — usually harmless |
