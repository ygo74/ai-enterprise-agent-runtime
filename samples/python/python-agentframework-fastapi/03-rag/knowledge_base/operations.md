# Knowledge Base Operations

This example builds an in-memory vector index from Markdown files in the
`knowledge_base` directory when the FastAPI application starts. The source files
remain the canonical content; the vector index is disposable and is rebuilt on
each process start.

The embedding model converts document chunks and search questions into vectors.
The retriever selects the most similar chunks, and the chat model drafts an
answer from those excerpts. The answer includes the source filenames so a caller
can inspect the supporting material.

Adding or changing Markdown files requires restarting the application. The
example uses one process-local index and is intended for local learning, not as
a durable or shared production vector database.