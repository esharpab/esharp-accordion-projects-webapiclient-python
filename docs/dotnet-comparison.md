# .NET Comparison

Both the Python and .NET clients expose the same API surface with idiomatic naming for their respective language.

## Side-by-Side

| Concept | .NET (`AccordionQ2Client`) | Python (`AccordionQ2Client`) |
|---------|---------------------------|------------------------------|
| Lifecycle | `IDisposable` / `using` | Context manager / `with` |
| Methods | `GetValueAsync(name)` | `get_value(name)` |
| Concurrency | `async` / `await` | Synchronous (thread-safe) |
| Nullability | `string?` | `None` |
| Config | `ChannelConfigRequest.Enabled = true` | `ChannelConfigRequest(enabled=True)` |
| Enums | `ChannelTypes.Analog` | `ChannelTypes.ANALOG` |
| Errors | `AccordionQ2ApiException` | `AccordionQ2ApiError` |
| Dependencies | Newtonsoft.Json | None (stdlib only) |
| Install | `dotnet add package AccordionQ2.WebApiClient` | `pip install accordionq2` |
| Package | [NuGet](https://www.nuget.org/packages/AccordionQ2.WebApiClient/) | [PyPI](https://pypi.org/project/accordionq2/) |

## Code Examples

=== "Python"

    ```python
    from accordionq2 import AccordionQ2Client

    with AccordionQ2Client("http://raspberrypi:5000") as client:
        status = client.connection.get_status()
        voltage = client.resources.get_value("Voltage.VDD")
        print(f"Connected: {status.is_connected}, VDD: {voltage}")
    ```

=== ".NET (C#)"

    ```csharp
    using AccordionQ2.WebApiClient;

    using var client = new AccordionQ2Client("http://raspberrypi:5000");
    var status = await client.Connection.GetStatusAsync();
    var voltage = await client.Resources.GetValueAsync("Voltage.VDD");
    Console.WriteLine($"Connected: {status.IsConnected}, VDD: {voltage}");
    ```

## When to Use Which

| Scenario | Recommended Client |
|----------|-------------------|
| Test automation scripts | Python |
| Raspberry Pi / embedded Linux | Python or .NET |
| ASP.NET services / Azure | .NET |
| Jupyter notebooks / data analysis | Python |
| Desktop applications (WPF, WinForms) | .NET |
| CI/CD pipelines | Either |
