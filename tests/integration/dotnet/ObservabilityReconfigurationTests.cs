using Xunit;
using Ygo74.AgentRuntime.Observability;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class ObservabilityReconfigurationTests
{
    [Fact]
    public void OpenTelemetrySetup_Returns_Exporter()
    {
        var exporter = OpenTelemetrySetup.ConfigureExporter("otlp");
        Assert.Equal("otlp", exporter);
    }
}
