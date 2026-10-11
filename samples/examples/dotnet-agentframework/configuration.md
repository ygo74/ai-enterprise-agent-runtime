# .NET Configuration

```csharp
var options = new EndpointOptions
{
    RouteKey = "demo",
    EnableChatCompletions = true,
    EnableStreaming = true
};
EndpointOptionsValidator.Validate(options);
```
