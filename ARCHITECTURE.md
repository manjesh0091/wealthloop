# Architecture

TODO: describe the LangGraph agent pipeline, state schema, and RAG flow.

## Agents
- ingestion_agent
- categorization_agent
- health_assessment_agent
- rag_agent
- recommendation_agent
- compliance_agent
- approval_gate
- execution_agent

## Compliance fail-then-retry loop

The compliance fail-then-retry loop is genuine, organically-triggerable
behavior — confirmed via repeated testing where Kabir's moderate-risk
allocation naturally exceeded the 40% equity cap and self-corrected on
retry. Due to LLM sampling variance, this doesn't trigger on every run; a
`DEMO_FORCE_FAIL_FOR` flag exists to guarantee this path fires during
recorded demos, without altering the underlying logic.
