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

## Requirements

| Requirement | Details |
|-------------|---------|
| Python      | 3.8 or later |
| Platform    | Windows, Linux (including ARM / Raspberry Pi) |
| Architecture | 32-bit and 64-bit |
| Dependencies | **None** &mdash; standard library only (`urllib`, `json`, `enum`, `dataclasses`) |

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
