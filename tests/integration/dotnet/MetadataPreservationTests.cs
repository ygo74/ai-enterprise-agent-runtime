using System.Collections.Generic;
using Xunit;
using Ygo74.AgentRuntime.Domains.Endpoints;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class MetadataPreservationTests
{
    [Fact]
    public void Metadata_Is_Preserved_In_Normalized_Request()
    {
        var meta = new Dictionary<string, object?> { ["model"] = "gpt-x", ["tenant"] = "acme" };
        var req = EndpointAdapters.Normalize("openai.responses", "r1", "demo", "hello", false, meta);

        Assert.NotNull(req.Metadata);
        Assert.Equal("gpt-x", req.Metadata!["model"]);
        Assert.Equal("acme", req.Metadata!["tenant"]);
    }
}
