# 05-rag: Local Knowledge Base RAG

This example builds a LangChain retrieval-augmented generation (RAG) agent over
the Markdown files in `knowledge_base/`. It uses OpenAI embeddings to index local
documents in an in-memory vector store, retrieves relevant chunks for each
question, and asks a chat model to answer from those excerpts with filename
citations. Both model calls use Azure OpenAI deployments.

The FastAPI app exposes OpenAI Responses (`/v1/responses`) and Chat Completions
(`/v1/chat/completions`) through the runtime's public `HostingFactory` API. Both
non-streaming and streaming requests use the same retrieval pipeline.
The hosting boundary returns `AgentOutput` with `TextContent`, or a typed
`ContentStart`/`TextDelta`/`ContentEnd`/`TerminalEvent` stream. Source filenames
and the appended `Sources:` section are preserved in both modes. The internal
LangChain model helper still produces text; no unused integration is installed.

## Prerequisites

- Python 3.12+
- Azure OpenAI resource with chat and embedding model deployments
- Azure OpenAI endpoint and API key

## Install

```powershell
cd docs/examples/python-langchain-fastapi/05-rag
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For development against the runtime source in this repository, set `PYTHONPATH`
after installing the framework requirements, to use the local runtime source:

```powershell
$env:PYTHONPATH="..\..\..\..\packages\python\security;..\..\..\..\packages\python\agents"
```

## Configure

```powershell
Copy-Item .env.sample .env
```

Set the Azure resource endpoint, API key, API version, and deployment names in
`.env`. `AZURE_OPENAI_CHAT_DEPLOYMENT` and
`AZURE_OPENAI_EMBEDDING_DEPLOYMENT` must be the deployment names created in your
Azure OpenAI resource, not the underlying model names. Use the resource endpoint
root, such as `https://<resource-name>.openai.azure.com`, without an `/openai/v1`
path; LangChain constructs the deployment API routes. Both deployments must
support the configured API version.

## Run

```powershell
python -m uvicorn openai_rag_app:app --reload --port 8005
```

The app creates document embeddings during startup, so the first startup sends
the local corpus to your Azure OpenAI embedding deployment. The vector index is
in memory and is rebuilt each time the process starts.

## Ask a Question

```powershell
$body = @{
  model = "enterprise-rag-demo"
  input = "How does this example protect against prompt injection in retrieved documents?"
  metadata = @{
    request_id = "rag-demo-001"
    route_key = "enterprise-rag-demo"
  }
  stream = $false
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8005/v1/responses" `
  -ContentType "application/json" `
  -Body $body
```

The answer should be grounded in `security.md` and include its filename as a
citation. To receive incremental output, change `stream` to `$true`; the runtime
formats the generated deltas as OpenAI-compatible Server-Sent Events. Chat
Completions is also available at `http://127.0.0.1:8005/v1/chat/completions`.

## Notes

- The sample corpus is intentionally small and inspectable. Add `.md` files to
  `knowledge_base/`; they are chunked and indexed at startup.
- Retrieved text is explicitly treated as untrusted evidence, not as instructions.
- The vector store is process-local and non-persistent. Use a durable vector
  database and appropriate access controls for production workloads.
- Requests are anonymous, matching the default setup in `01-get-started`; do not
  expose the sample publicly with real or sensitive documents.