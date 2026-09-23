// Copyright (c) Microsoft. All rights reserved.

using Microsoft.Agents.AI;

namespace ReferenceAgent.Rag;

/// <summary>
/// A tiny, in-memory "knowledge base" standing in for a real retrieval backend (a vector database,
/// a search index, etc.). This is the RAG capability demo: it is wired into the agent as a
/// <see cref="TextSearchProvider"/> (see Program.cs), which injects matching snippets into context
/// before the model responds - the same mechanism a production RAG integration uses, just with a
/// keyword match instead of a real retriever.
/// </summary>
internal static class FaqSearch
{
    private static readonly (string Question, string Answer)[] s_entries =
    [
        ("refund", "Refunds are processed within 5 business days of an approved return."),
        ("support hours", "Support is available 9am-5pm CET, Monday to Friday."),
        ("shipping", "Standard shipping takes 3-7 business days within the country of purchase."),
        ("warranty", "All products carry a 2-year manufacturer warranty from the date of purchase."),
    ];

    public static Task<IEnumerable<TextSearchResult>> SearchAsync(string query, CancellationToken cancellationToken)
    {
        string[] queryWords = query.ToLowerInvariant().Split(' ', StringSplitOptions.RemoveEmptyEntries);

        IEnumerable<TextSearchResult> results = s_entries
            .Where(entry => queryWords.Any(word => entry.Question.Contains(word, StringComparison.OrdinalIgnoreCase)))
            .Select(entry => new TextSearchResult(entry.Answer)
            {
                Name = entry.Question,
                SourceName = "reference-agent-faq",
            });

        return Task.FromResult(results);
    }
}
