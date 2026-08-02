using System;
using System.IO;
using System.Text.Json;
using Xunit;

namespace Ygo74.AgentRuntime.Tests.Performance;

public sealed class PerformanceBudgetTests
{
    [Fact]
    public void PerformanceBudget_Baseline_File_Is_Valid()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "performance_thresholds.json");
        Assert.True(File.Exists(path));

        var json = File.ReadAllText(path);
        using var doc = JsonDocument.Parse(json);
        Assert.True(doc.RootElement.GetProperty("normalization_dispatch_p95_ms").GetInt32() > 0);
    }
}
