# Remaining Discovery Validation Scenarios

Use these scenarios when completing the open discovery tasks in
[`TASKS.md`](../TASKS.md). Current behavior and limits remain in the
[consolidated discovery specification](../../../discovery/agent-catalog.md).

## Descriptor declaration and validation

Declare two descriptors through the supported configuration path and bind each
to a registered route. Verify registry lookup and documented defaults. Then
verify that duplicate public IDs and capability claims that contradict the
route configuration fail during initialization with actionable errors. Verify
that a registered route with no explicit descriptor receives the documented
minimal default where supported.

## Provider listings and invocation round trips

For every discoverable descriptor, request the OpenAI and Anthropic listings,
including the shared-path dialect selector and an Anthropic page smaller than
the catalogue. Verify envelopes, display names, timestamps, continuation
indicators, extension fields, exact ordering, single-model lookup, and
structured invalid-request errors. Submit each returned ID as the invocation
model and verify it resolves to the same route. Include unknown IDs,
case-changed IDs, whitespace-padded IDs, and an empty catalogue.

## A2A card consistency

Declare a descriptor with skills, capabilities, documentation URL, and
authentication scheme names. Compare its agent card with the OpenAI and
Anthropic single-model projections for every shared field. Verify the public
base URL is used for advertised routes, no secret is exposed, and disabling the
card returns the documented not-found response without disabling model
discovery.

## Discovery access control

Verify public and authenticated discovery modes. For an authenticated caller,
exercise a visibility rule that hides one descriptor and confirm it is absent
from listings and indistinguishable from an unknown descriptor in direct
lookup. Verify hidden descriptors remain directly invocable when application
policy allows it. Verify rule exceptions and deadline expiry fail closed and
are logged without sensitive data.

## Performance and parity

Load 100 descriptors, measure listing p95 against the 20 ms budget, and verify
single lookup uses the indexed registry. Use equivalent descriptor sets in
Python, .NET, and Java and compare supported provider/card fields. Record
unimplemented language surfaces as gaps rather than passing parity.
