---
name: user-docs
description: Create or update simple-English Markdown documentation for users and operators, with shared runtime concepts, practical HTTP/JSON examples, and a conceptual end-to-end agent walkthrough. Use for installation, configuration, operation, and user workflows; contributor architecture and feature specifications belong to the other documentation skills.
---

# User Documentation

Write documentation for people who install, configure, or use the repository's
runtime and agents. Use simple English for readers working in a French-speaking
environment. Explain product terms before using them and preserve exact shared
protocol, configuration, and API names.

## Where to write

- Put shared user and operator documentation under `doc/users/`.
- Keep the reading order in `doc/users/README.md`: installation; bring-your-own
  agent concepts; hosting; endpoints and outputs; framework integrations;
  conversations; agent, skill, and MCP configuration; human approval; MCP server
  hosting; security; discovery.
- Keep `doc/users/` language-neutral. Shared HTTP/JSON examples are allowed, but
  do not include language-specific code or installation/run commands there.
- Put implementation code, package setup, and language-specific behavior in the
  relevant `doc/<language>/` guide. Python details belong in `doc/python/`.
- Keep contributor architecture in `doc/contributors/` and feature rationale
  in `spec/`; link to those pages instead of mixing audiences.
- Runnable examples belong under `samples/<language>/`. Maintain
  `samples/README.md` as the language catalog index and a project README for each
  language catalog. Add a language link when that catalog has actual samples;
  do not create empty language directories.
- Link each example from its shared domain page and from its language catalog.

## Domain pages and examples

Every domain page must include at least one practical example grounded in the
supported runtime behavior. Shared pages may use neutral HTTP/JSON requests and
responses. Language-specific code, package installation, and commands belong in
the corresponding language guide or sample README. Verify names and behavior
against source, configuration, existing examples, and documentation. Do not
invent options or promise behavior that has not been confirmed.

For examples:

- Mark values that operators must supply, and never include real secrets.
- State prerequisites and where a language-specific command should be run in
  its implementation guide or sample README.
- Explain expected output and what to do when an operation fails.
- Prefer complete, internally consistent examples over disconnected fragments.

## Complete agent walkthrough

Maintain a conceptual worked guide at `doc/users/complete-agent.md`. Follow a
request through the shared concepts the repository supports, including agent
instructions, business rules, tools, skills, hosting, authentication,
discovery, conversations, approvals, and output projection where applicable.
Link to runnable language-specific examples for implementation details. State
when a feature is unsupported, cannot be combined with the selected design, or
needs an external service. Keep secrets as placeholders. Do not put
language-specific code or setup commands in this guide.

## Writing and review

- Use direct, friendly language, short paragraphs, and numbered steps for
  procedures.
- Explain defaults, limits, permissions, errors, and operational effects where
  they matter to a user's decision.
- Use Markdown headings and fenced code blocks with suitable language labels.
- Link to the relevant domain page, complete example, API contract, or support
  notes using repository-relative paths.
- Check links, commands, configuration names, and examples. Do not run tests
  solely to write documentation unless the user asks for them.
