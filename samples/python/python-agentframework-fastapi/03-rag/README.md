# 03 — Local knowledge-base RAG with MAF

This example combines lexical retrieval over local Markdown files with a
native MAF agent. The MAF function tool returns the best matching passages;
the model answers from that evidence and names the source files. Retrieved
documents are treated as untrusted evidence, not as agent instructions.

## Requirements and run

Use Python 3.12 or newer and an OpenAI API key. From this directory:

```powershell
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "<your-openai-key>"
python -m uvicorn app:app --host 127.0.0.1 --port 8103
```

## Ask a question

```shell
curl http://127.0.0.1:8103/ask \
  -H 'content-type: application/json' \
  -d '{"question":"How does the runtime protect an operation with a side effect?"}'
```

The response contains an answer with the matching filenames. The local search
scores document overlap; replace it with an embedding index when a production
application needs semantic retrieval or a larger corpus. This example uses a
developer-owned API. See [native agent hosting](../04-native-agent/README.md)
for the runtime's standard HTTP endpoints.
