# AI Cost Analysis

## Pricing Snapshot

Pricing changes over time, so this analysis records the assumptions used for the final submission package on 2026-05-04.

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

The Week 2 document flow adds OCR/extraction/review work, but the current submitted slice uses deterministic synthetic text/PDF extraction and does not add paid model calls by default.

## Actual Development AI Spend

Paid metered AI API spend attributable from this repository: **$0.00 recorded**.

Reasoning:

- Automated API tests default to the mock provider and deterministic fixtures.
- Local vector tests default to hash embeddings unless OpenAI embeddings are explicitly configured.
- Week 2 document extraction tests use deterministic synthetic fixtures.
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

Production should not run every question through the strongest available model. The expected routing mix is:

| Route | Share | Model cost behavior |
|---|---:|---|
| Deterministic structured answer | 40% | No LLM call; answer from verified FHIR/evidence objects. |
| Simple source-backed summary | 50% | Lowest-cost eval-approved model. |
| Broad note synthesis or verifier retry | 10% | Stronger eval-approved model with a strict output cap. |

Using that mixed route with the prices above:

```text
Cheap model route:
  Input:  0.36M tokens * $0.75/M = $0.27 / user / month
  Output: 0.036M tokens * $4.50/M = $0.16 / user / month

Strong model route:
  Input:  0.072M tokens * $5.00/M  = $0.36 / user / month
  Output: 0.0072M tokens * $30.00/M = $0.22 / user / month

Embeddings: 0.18M * $0.13/M = $0.02 / user / month
Estimated routed AI total:   $1.03 / user / month
```

This is the production target to defend in review: the agent uses retrieval and deterministic verification to avoid model spend, then pays for larger models only when the clinical question actually needs broad synthesis or a retry after verifier failure.

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

Using the routed production mix above gives a more realistic target:

| Active users | Routed AI/month | Infra + observability/month | Estimated total/month |
|---:|---:|---:|---:|
| 100 | $103 | $150-$500 | $253-$603 |
| 1,000 | $1,031 | $1,500-$3,500 | $2,531-$4,531 |
| 10,000 | $10,314 | $15,000-$35,000 | $25,314-$45,314 |
| 100,000 | $103,140 | $150,000-$300,000 | $253,140-$403,140 |

## Cost Controls

- Keep retrieval budgets small: use pgvector to find evidence, then call FHIR source endpoints only for selected evidence.
- Cache evidence with short TTLs and revalidate before use.
- Use prompt caching for stable system instructions, schemas, and tool descriptions.
- Use batch embedding jobs for nightly reindexing when latency is not user-facing.
- Route simple deterministic answers to source-backed fallback when no LLM is needed.
- Track per-tenant token usage, vector storage growth, cache hit rate, and verifier rejection rate.
- Require explicit approval before enabling a provider for real PHI.
- Keep OpenRouter and open-source hosted models available for synthetic-data economics and eval comparison, but do not enable them for real PHI until contractual and data-policy gates pass.
- Record provider, model, token counts, cache-hit flags, latency, verifier outcome, and estimated cost for every model call.

## Latency And Concurrency

The latency target for common chart questions is under 5 seconds p95 after authentication. The request path should stream status immediately, retrieve structured evidence first, run vector search only for note/document questions, cap evidence count, cap output tokens, and fail with a clear verified message if the provider or verifier cannot complete safely.

Redis is useful once the system has more than one API replica or repeat traffic starts to hit OpenEMR/FHIR hard. Redis should hold only rebuildable operational state:

- 30-60 second JWKS/token-validation cache.
- Clinician-scoped patient roster and schedule prefetch cache.
- Per-tenant rate-limit and concurrency counters.
- Idempotency keys for document uploads, reindex jobs, and write retries.
- Distributed locks for patient reindex and document extraction.
- SSE/job progress fanout for long-running extraction.

Redis should not become the clinical source of truth and should not cache final clinical answers. Postgres remains the source for encrypted evidence, audit, conversations, vector chunks, job state, and approved extracted facts.

At 1,000 clinicians hitting the agent at the same time, the first risk is provider and OpenEMR backpressure, not Python CPU. The production posture is admission control: reject or queue over-budget LLM calls, reserve deterministic/FHIR-only paths, isolate workers from chat API replicas, and expose queue depth and model-provider saturation in `/api/status`.

At 10,000 concurrent clinicians, the model layer should behave like a gateway rather than a direct SDK call: provider health checks, tenant budgets, circuit breakers, retry budgets, and downgrade routes from strong model to cheap model to deterministic refusal. Database work needs tuned indexes, pgvector HNSW, partitioned telemetry/audit tables, and read replicas for non-critical dashboards.

## Architecture Changes By Scale

At 100 users, the current Railway suite is reasonable if PHI contractual requirements are satisfied and backups, secrets, audit retention, and dependency scanning are enforced.

At 1,000 users, the worker should be isolated from the request path, reindexing should run through a durable queue, Redis should provide hot-path caches and distributed locks, and observability should include latency SLOs, token spend alerts, and failed-verifier dashboards.

At 10,000 users, pgvector should move to a tuned production database tier or a dedicated vector service. The model adapter should become a gateway that supports provider failover, circuit breakers, rate-limit shaping, tenant quotas, cached prompts, and cost-aware model routing.

At 100,000 users, the system needs negotiated model pricing or self-hosted inference economics, multi-region redundancy, sharded patient indexes, formal incident response, and enterprise compliance controls beyond the hackathon deployment.
