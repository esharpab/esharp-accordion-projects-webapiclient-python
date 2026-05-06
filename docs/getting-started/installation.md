# Installation

## From PyPI (recommended)

```bash
pip install accordionq2
```

## From Source

Clone the repository and install in editable mode (recommended during development):

```bash
git clone https://github.com/esharpab/esharp-accordion-projects-webapiclient-python.git
cd esharp-accordion-projects-webapiclient-python
pip install -e .
```

Or install without editable mode:

```bash
pip install .
```

## Using uv (recommended for development)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager:

```bash
# Install uv
pip install uv

# Create a virtual environment and install the package
uv venv
uv pip install -e .
```

## Development Setup

Install with all development dependencies (linting, type checking, tests):

```bash
pip install -e ".[dev]"
```

This installs:
- **pytest** &mdash; test runner
- **ruff** &mdash; linter and formatter
- **mypy** &mdash; static type checker
- **pre-commit** &mdash; git hook runner

To activate pre-commit hooks:

```bash
pre-commit install
```

## Requirements

| Requirement | Details |
|-------------|---------|
| Python      | 3.11 or later |
| Platform    | Windows, Linux (including ARM / Raspberry Pi), macOS |
| Architecture | 32-bit and 64-bit |
| Dependencies | **None** &mdash; standard library only (`http.client`, `json`, `ssl`, `threading`, `dataclasses`) |

## Verifying the Installation

```python
import accordionq2
print(accordionq2.__version__)
```

## .NET Alternative

If you are working in a .NET environment, the equivalent package is available on NuGet:

```shell
dotnet add package AccordionQ2.WebApiClient
```

See the [.NET comparison](../dotnet-comparison.md) for a side-by-side feature comparison.
