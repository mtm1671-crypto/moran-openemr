# AI Cost Analysis

## Pricing Snapshot

Pricing changes over time, so this analysis records the assumptions used for the final submission package on 2026-05-03.

Sources:

- OpenAI API pricing: https://openai.com/api/pricing/
- OpenAI embedding pricing: https://platform.openai.com/docs/pricing/
- Railway pricing: https://docs.railway.com/pricing
- OpenRouter NVIDIA provider page: https://openrouter.ai/provider/nvidia

Relevant prices used:

| Item | Price used |
|---|---:|
| GPT-5.5 input | $5.00 / 1M tokens |
| GPT-5.5 cached input | $0.50 / 1M tokens |
| GPT-5.5 output | $30.00 / 1M tokens |
| GPT-5.4 mini input | $0.75 / 1M tokens |
| GPT-5.4 mini output | $4.50 / 1M tokens |
| `text-embedding-3-large` | $0.13 / 1M tokens |
| Railway Pro subscription | $20 / month plus usage |
| Railway RAM | $10 / GB / month |
| Railway CPU | $20 / vCPU / month |
| Railway egress | $0.05 / GB |
| Railway volume storage | $0.15 / GB / month |

The current deployed synthetic-data demo can use `nvidia/nemotron-3-super-120b-a12b:free` through OpenRouter. That path is useful for demo economics, but it is not counted as a production PHI path. Real PHI should use a HIPAA-appropriate provider path with the required contractual controls, or a self-hosted model environment.

## Actual Development AI Spend

Paid metered AI API spend attributable from this repository: **$0.00 recorded**.

Reasoning:

- Automated API tests default to the mock provider and deterministic fixtures.
- Local vector tests default to hash embeddings unless OpenAI embeddings are explicitly configured.
- The deployed demo configuration uses OpenRouter's free Nemotron model for synthetic data.
- No provider billing export is committed to the repository.

This excludes any personal ChatGPT/Codex subscription cost, human engineering time, and Railway infrastructure spend. Before final upload, check the OpenAI/OpenRouter/Railway dashboards; if any paid provider calls were made outside the repo-tracked paths, replace this line with the dashboard total and attach the screenshot/export in the submission notes.

## Workload Assumptions

The production estimate treats one "user" as one active clinical user.

| Assumption | Value |
|---|---:|
| Clinic days per month | 20 |
| Chart questions per user per day | 12 |
| Chart questions per user per month | 240 |
| Average model input per question | 3,000 tokens |
| Average model output per question | 300 tokens |
| Monthly model input per user | 720,000 tokens |
| Monthly model output per user | 72,000 tokens |
| Monthly new/reindexed embedding tokens per user | 180,000 tokens |

The estimates below ignore cached-input discounts to stay conservative. Prompt caching, smaller models, batching, and stricter retrieval budgets can reduce cost.

## Variable AI Cost

Using GPT-5.5 for the final answer step:

```text
Input:  0.72M tokens * $5.00/M  = $3.60 / user / month
Output: 0.072M tokens * $30.00/M = $2.16 / user / month
LLM total:                         $5.76 / user / month
Embeddings: 0.18M * $0.13/M      = $0.02 / user / month
Estimated AI total:                $5.78 / user / month
```

Lower-cost alternative after eval approval, using GPT-5.4 mini:

```text
Input:  0.72M tokens * $0.75/M = $0.54 / user / month
Output: 0.072M tokens * $4.50/M = $0.32 / user / month
Embeddings:                       $0.02 / user / month
Estimated AI total:               $0.89 / user / month
```

## Production Cost Projection

| Active users | GPT-5.5 AI/month | Infra + observability/month | Estimated total/month | Architecture needed |
|---:|---:|---:|---:|---|
| 100 | $578 | $150-$500 | $728-$1,078 | Current Railway shape is enough: web, API, worker, OpenEMR, Postgres/pgvector, backups, structured logs. |
| 1,000 | $5,783 | $1,500-$3,500 | $7,283-$9,283 | Split worker from API, add queue-backed reindexing, tune Postgres indexes, add log retention and alerting. |
| 10,000 | $57,834 | $15,000-$35,000 | $72,834-$92,834 | Dedicated Postgres/pgvector cluster, read replicas, async ingestion pipeline, model gateway, stronger SLO monitoring. |
| 100,000 | $578,340 | $150,000-$300,000 | $728,340-$878,340 | Multi-region service deployment, sharded vector index, durable event streams, dedicated security/compliance operations, negotiated inference pricing or self-hosted GPU fleet. |

Using the GPT-5.4 mini alternative after it passes the same eval gates would reduce estimated monthly AI cost to about:

| Active users | GPT-5.4 mini AI/month |
|---:|---:|
| 100 | $89 |
| 1,000 | $887 |
| 10,000 | $8,870 |
| 100,000 | $88,700 |

## Cost Controls

- Keep retrieval budgets small: use pgvector to find evidence, then call FHIR source endpoints only for selected evidence.
- Cache evidence with short TTLs and revalidate before use.
- Use prompt caching for stable system instructions, schemas, and tool descriptions.
- Use batch embedding jobs for nightly reindexing when latency is not user-facing.
- Route simple deterministic answers to source-backed fallback when no LLM is needed.
- Track per-tenant token usage, vector storage growth, cache hit rate, and verifier rejection rate.
- Require explicit approval before enabling a provider for real PHI.

## Architecture Changes By Scale

At 100 users, the current Railway suite is reasonable if PHI contractual requirements are satisfied and backups, secrets, audit retention, and dependency scanning are enforced.

At 1,000 users, the worker should be isolated from the request path, reindexing should run through a durable queue, and observability should include latency SLOs, token spend alerts, and failed-verifier dashboards.

At 10,000 users, pgvector should move to a tuned production database tier or a dedicated vector service. The model adapter should become a gateway that supports provider failover, rate-limit shaping, tenant quotas, and cached prompts.

At 100,000 users, the system needs negotiated model pricing or self-hosted inference economics, multi-region redundancy, sharded patient indexes, formal incident response, and enterprise compliance controls beyond the hackathon deployment.
