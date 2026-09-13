"""An OpenAI-compatible agent whose tool call waits for a human answer.

This is the example the whole ``humanapproval`` domain exists for.

An OpenAI-compatible API answers every request. A turn therefore cannot hold
while a person decides, which is the awkward part of human-in-the-loop over HTTP:
the obvious implementation blocks the connection, and the obvious workaround
loses the operation. Neither is acceptable.

What happens instead:

1. the model asks for the gated tool, and the graph suspends;
2. the turn **ends having changed nothing**, and the reply says what is waiting
   and how to answer it;
3. the person replies ``CONFIRM cfm-xxxx`` in a later request;
4. that text is read by a literal parser **before the model sees it**, the ticket
   is claimed, and the suspended graph is resumed from the arguments stored on
   the ticket.

The property worth stating twice: the model describes the operation, then plays
no part in running it. It cannot alter the arguments between the description and
the execution, because they never come back through it.

Run it with::

    uvicorn openai_responses_app:app --reload --port 8000
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from langgraph_approval import LangGraphApprovalBridge
from solution_architect_agent import OPERATIONS, answer_of, build_agent, interrupts_of

from env_loader import ensure_env_loaded
from ygo74.agent_runtime import (
    AdvertisedSecurity,
    AgentDescriptorFactory,
    AgentManifest,
    ConfirmationCommandParser,
    ConfirmationDetail,
    ConfirmationRequest,
    ConfiguredConfirmationPolicy,
    ConfirmationTicket,
    DescriptorRegistry,
    DiscoveryConfiguration,
    InMemoryConfirmationPreferenceStore,
    InMemoryPendingConfirmationStore,
    PendingConfirmationRenderer,
    ResolvedUser,
    SecurityFloor,
    SkillManifest,
    StaticApiKeyUserResolver,
    UnknownTicketError,
    UserContext,
    add_ai_endpoints,
    latest_message,
)

ensure_env_loaded()
logging.basicConfig(level=logging.INFO)

AGENT_ID = "ai-solution-architect-hitl"
API_KEY = "demo-key"

app = FastAPI(title="AI Solution Architect - human in the loop")

# One process, one demonstration. A deployment behind several workers needs a
# shared, atomic store: a ticket issued on one worker is unclaimable on another,
# and a restart loses every pending approval.
tickets = InMemoryPendingConfirmationStore()
parser = ConfirmationCommandParser()
renderer = PendingConfirmationRenderer()
bridge = LangGraphApprovalBridge()

# Nothing is placed below the floor here: the deployment is free to pre-approve
# the research call. Passing an empty floor is a decision somebody wrote down,
# which is why the argument is required rather than defaulted.
policy = ConfiguredConfirmationPolicy(InMemoryConfirmationPreferenceStore(), SecurityFloor(()))

# The graph is kept per conversation, because a suspended graph is resumed by
# thread id and the arguments live in its checkpoint.
_agents: dict[str, Any] = {}

# Which tickets a suspended turn is waiting on, in the order the framework will
# match decisions to actions, and the answers collected so far. A turn that
# suspended two operations needs two answers before it resumes.
_awaiting: dict[str, list[str]] = {}
_answers: dict[str, dict[str, bool]] = {}

# Left as ``None`` in normal use, so the agent builds its own model from the
# environment. Set it to drive the approval path without reaching a provider:
# everything this example demonstrates happens around the model, not inside it.
MODEL_OVERRIDE: Any | None = None


def _user_of(payload: dict[str, Any]) -> UserContext:
    """Who this request is acting for, and in which conversation.

    Read from ``auth_context`` - populated by the runtime from the verified
    credential - never from the body: a caller must not be able to name
    themselves, and the subject is what tickets are partitioned by.
    """
    context = payload.get("auth_context") or {}
    identity = context.get("identity") or {}
    subject = str(identity.get("subject") or context.get("userId") or "")
    conversation = str((payload.get("metadata") or {}).get("conversation_id") or "default")
    return UserContext(user_id=subject, session_id=conversation, permissions=frozenset())


def _agent_for(user: UserContext) -> Any:
    key = _conversation_key(user)
    if key not in _agents:
        _agents[key] = build_agent(policy, user, model=MODEL_OVERRIDE)
    return _agents[key]


def _thread(user: UserContext) -> dict[str, Any]:
    """State is keyed by the authenticated subject first.

    A caller supplying somebody else's conversation identifier reaches their own
    graph, never that person's.
    """
    return {"configurable": {"thread_id": f"{user.user_id}:{user.session_id}"}}


def _request_for(user: UserContext, approval: Any) -> ConfirmationRequest:
    """Describe, in the user's terms, what the model is asking to do.

    The query is shown because it *is* the decision: what leaves the
    organisation is the question itself, not the fact that a search happened.
    """
    query = str(approval.arguments.get("query", "")).strip()
    return ConfirmationRequest(
        request_id=f"req-{user.session_id}-{approval.tool_name}",
        operation=OPERATIONS[0],
        requested_for=user.user_id,
        title="Send this question to Microsoft Learn",
        target=approval.tool_name,
        details=(ConfirmationDetail(label="Query", value=query),) if query else (),
    )


async def _resume(user: UserContext, decisions: list[dict[str, Any]]) -> str:
    """Hand the collected answers back to the graph, in action order."""
    agent = _agent_for(user)
    result = await agent.ainvoke(bridge.resume_command(decisions), _thread(user))
    return answer_of(result)


async def _start(user: UserContext, message: str) -> str:
    """Run one turn, and stop rather than perform anything that was gated."""
    key = _conversation_key(user)
    if _awaiting.get(key):
        # The graph is suspended. Starting another turn on the same thread would
        # either fail or silently abandon the operation the person is still being
        # asked about, so the question is repeated instead.
        return "Something is still waiting for your answer." + renderer.render(_pending_tickets(user))

    agent = _agent_for(user)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": message}]}, _thread(user))

    approvals = bridge.pending_approvals(interrupts_of(result))
    if not approvals:
        return answer_of(result)

    # One ticket per suspended call, in the order the framework will match
    # decisions to actions. Answering one must not answer the others, so the
    # order is remembered rather than rediscovered.
    issued = [
        ConfirmationTicket.issue(
            subject=user.user_id,
            conversation_id=user.session_id,
            tool_name=approval.tool_name,
            request=_request_for(user, approval),
            arguments=approval.arguments,
        )
        for approval in approvals
    ]
    for ticket in issued:
        tickets.issue(ticket)
    _awaiting[key] = [ticket.ticket_id for ticket in issued]
    _answers[key] = {}

    return "I need your approval before going further." + renderer.render(issued)


async def _answer(payload: dict[str, Any]) -> dict[str, Any]:
    user = _user_of(payload)
    message = latest_message(payload.get("input"))

    # Before the model, always. An approval the model saw first would be an
    # approval the model could reinterpret.
    command = parser.parse(message)
    if command is None:
        output = await _start(user, message)
    else:
        output = await _honour(user, command)

    return {
        "request_id": payload.get("request_id", ""),
        "status": "success",
        "output": output,
        "metadata": {"route_key": payload.get("route_key", "")},
    }


async def _honour(user: UserContext, command: Any) -> str:
    """Claim the ticket the command names, record the answer, resume when complete.

    Claiming first is deliberate: a refusal consumes the ticket too, so a
    declined operation cannot be confirmed a moment later by repeating the
    identifier.

    The graph is only resumed once *every* suspended call has been answered. A
    turn that suspended two operations therefore needs two answers, and
    confirming one of them does not run the other - which is the whole point of
    issuing a ticket per operation rather than one per turn.
    """
    try:
        tickets.claim(command.ticket_id, subject=user.user_id, conversation_id=user.session_id)
    except UnknownTicketError:
        # Deliberately the same answer whether the ticket never existed, was
        # already used, expired, or belongs to somebody else.
        return "That confirmation is not awaiting an answer."

    key = _conversation_key(user)
    order = _awaiting.get(key, [])
    answers = _answers.setdefault(key, {})
    answers[command.ticket_id] = command.approves

    outstanding = [ticket_id for ticket_id in order if ticket_id not in answers]
    if outstanding:
        return "Recorded." + renderer.render(_pending_tickets(user))

    decisions = [{"type": "approve"} if answers[ticket_id] else {"type": "reject"} for ticket_id in order]
    approved = [ticket_id for ticket_id in order if answers[ticket_id]]
    _forget(user)

    answer = await _resume(user, decisions)
    if approved:
        return answer
    return "Cancelled. Nothing was sent."


def _conversation_key(user: UserContext) -> str:
    """Bookkeeping key, subject first for the same reason the thread id is."""
    return f"{user.user_id}:{user.session_id}"


def _pending_tickets(user: UserContext) -> list[ConfirmationTicket]:
    """The tickets of this conversation that are still unanswered."""
    return list(tickets.pending(subject=user.user_id, conversation_id=user.session_id))


def _forget(user: UserContext) -> None:
    """Drop what is left once a suspended turn has been fully answered.

    Without this, a ticket from a finished turn stays claimable until it expires,
    and claiming it would resume a graph that has nothing suspended.
    """
    key = _conversation_key(user)
    _awaiting.pop(key, None)
    _answers.pop(key, None)
    tickets.discard(subject=user.user_id, conversation_id=user.session_id)


def entrypoint(payload: dict[str, Any]) -> Any:
    """Answer one request. Streaming is off: an approval is not a token stream."""
    return _answer(payload)


manifest = AgentManifest(
    name="AI Solution Architect (human in the loop)",
    description="Answers Azure architecture questions, asking before it queries Microsoft Learn.",
    instructions="Ask before sending a question outside the organisation.",
    skills=(
        SkillManifest(
            tool_name="mslearn_mcp_search",
            implementation="mslearn_mcp_search",
            description="Searches Microsoft Learn. Requires an explicit approval before each call.",
            operation=OPERATIONS[0],
        ),
    ),
)

api_key_resolver = StaticApiKeyUserResolver({API_KEY: ResolvedUser(user_id="demo-user", name="Demo User")})

add_ai_endpoints(
    app,
    entrypoint,
    default_route_key=AGENT_ID,
    enable_openai_chat_completions=True,
    enable_openai_responses=True,
    enable_anthropic_messages=False,
    require_bearer_token=True,
    api_key_resolver=api_key_resolver,
    descriptor_registry=DescriptorRegistry(
        [
            AgentDescriptorFactory(
                manifest,
                agent_id=AGENT_ID,
                tags=("solution-architecture", "human-in-the-loop"),
                created_at=datetime(2026, 9, 13, tzinfo=timezone.utc),
                # Derived from the resolver above, so the descriptor cannot
                # advertise a door this service does not have.
                security=AdvertisedSecurity.of(jwt_validation=None, api_key_resolver=api_key_resolver),
                owner="ai-enterprise-agent-runtime",
            ).build()
        ]
    ),
    discovery=DiscoveryConfiguration(enable_openai_models=True, require_authentication=True),
)
