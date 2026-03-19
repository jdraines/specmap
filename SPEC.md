Initial Design Idea & Spec for new project called `specmap`
===========================================================

Motivation
----------

In the age of agentic coding, AI is generating tons of code, but humans still need to review that code (or at least be able to if needed). The amount of code being generated makes this an incredibly difficult task sometimes. Tools like Graphite which stack PRs help in one aspect, but in another way, they just make it easier to create MORE code, which only increases this particular problem.

However, one aspect of the AI-coding era is that development tends to be spec-driven: either a user creates a markdown file to guide a coding agent, or a coding agent writes a markdown file to persist a plan across subagents or sessions, or else a user asks an agent for a spec after conversation. All of these are common. And the result of this pattern is that the code that is generated *should* in some way map to the spec that was generated. That is, for any given line or block of code, there should be some sort of human-readable text that explains the purpose of that code.

If we could make an interface that makes it easy for a reviewer to look at proposed code changes (i.e. in a PR-like context) and have text from a spec available immediately next to each change (possibly a side panel that is populated on hover or is static, or is clickable, etc.) then as users review code, there would be a clear description of what everything is and does immediately there. This could improve developer review of AI generated code, as well as code reviewer experience in orienting to a code base or orienting to the changes.

Requirements
------------

* Specs that are generated during agentic coding sessions have specific contents tagged so that they map to code changes. (Current requirement is data structure and persistence-agnostic, so we can develop this concept for what will perform best.)
* Code changes that lack spec context can have supplemental spec context generated
* The capability for spec tagging and supplementation should be accessible via ANY existing coding agent like Claude Code, Codex, Opencode, Cursor, Copilot, etc. This means that the capability likely needs to be MCP-based. Users who use the tool should load the MCP server, and we should ensure that the coding agent uses it.
* Spec tagging and supplementation should be optimized so that it doesn't inflate token costs -- this may mean only doing it at certain checkpoints within a coding session or possibly as a large indexing-run which occurs when a PR is ready for review (and then updpated as any changes come in.) This concept should be developed further.
* A user interface should integrate with GitHub to support comments and actions like approvals.
* The user interface should allow a review to look at code changes and immediately see spec text (or a summary of spec text?) that corresponds to that change. I mentioned earlier something like a side panel that populates on hover?
* Auth should be OAuth and initially only uses GitHub. This should enable us to ensure identities and also connect us to a GitHub account where we can access PRs.
* Scale: Imagine that this is going to be a startup that will take off rapidly and we'll need to scale rapidly.
* Security: Follow absolute best practices and do not cut corners.

Design Requirements
-------------------

* Design should clearly distinguish providers from core logic and should use pluggable interfaces for providers.
* Backend may be written in Python if performance is not an issue, or Go if we are concerned about performance.
* UI should be a Typescript React app.

Non-goals
---------

* Don't try to support stacked PR tooling like graphite for now
* Don't try to support git platform providers other than GitHub for now (but organize code in a pluggable way)


Deployment
----------

* Initial deployment should attempt to use a service that will abstract deployment concerns if possible so that we're not managing our own infra to start with.
