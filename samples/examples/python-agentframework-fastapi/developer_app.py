"""Developer-owned FastAPI host for a normal Microsoft Agent Framework agent."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from native import create_agent


class AskRequest(BaseModel):
    """Question accepted by the application route."""

    question: str = Field(min_length=1)


app = FastAPI(title="Native MAF agent - developer-owned API")
agent = create_agent()


@app.post("/ask")
async def ask(request: AskRequest) -> dict[str, str]:
    """Run the MAF agent and return the application's response shape."""
    response = await agent.run(request.question)
    return {"answer": response.text or ""}
