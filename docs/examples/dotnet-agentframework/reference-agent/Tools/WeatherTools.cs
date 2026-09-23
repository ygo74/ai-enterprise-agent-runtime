// Copyright (c) Microsoft. All rights reserved.

using System.ComponentModel;

namespace ReferenceAgent.Tools;

/// <summary>
/// Deterministic sample tools. Deterministic so the sample's behavior does not depend on a real
/// weather service, and so <see cref="SendWeatherAlert"/>'s approval gate is the only source of
/// non-determinism a caller needs to reason about.
/// </summary>
internal static class WeatherTools
{
    [Description("Gets the current weather for a given location.")]
    public static string GetWeather(
        [Description("The city and, optionally, region or country, e.g. 'Paris' or 'Paris, France'.")] string location)
    {
        string[] conditions = ["sunny", "cloudy", "rainy", "windy", "clear"];
        int index = Math.Abs(location.GetHashCode()) % conditions.Length;
        int temperatureCelsius = 8 + (Math.Abs(location.GetHashCode()) % 20);
        return $"The weather in {location} is {conditions[index]} with a high of {temperatureCelsius}\u00b0C.";
    }

    // Wrapped in ApprovalRequiredAIFunction in Program.cs: this represents a side-effecting action
    // (sending a notification) rather than a read, which is why it is the tool gated behind human
    // approval in this sample.
    [Description("Sends a weather alert message to subscribers of a location. This notifies real people: use only when asked to.")]
    public static string SendWeatherAlert(
        [Description("The location the alert concerns.")] string location,
        [Description("The alert message to send.")] string message)
        => $"Alert sent to subscribers in {location}: {message}";
}
