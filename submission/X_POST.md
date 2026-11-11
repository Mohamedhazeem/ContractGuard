# X post — shot notes and caption

## The caption (paste this)

```
HTTP 200 is not proof your API is correct.

ContractGuard is a Hermes plugin that validates requests and live responses
against your OpenAPI contract — before the request is sent, and after.

In this demo the API returns price as a string while the contract says
number. Ordinary tests pass. ContractGuard does not.

It rejects the bad request before dispatch (request_sent: false), then fails
the live endpoint on $.price even though the status is 200. Same check, same
spec hash, after the fix: PASS.

Built for agents: natural-language prompts, deterministic verdicts
(PASS / FAIL / BLOCKED / INCOMPLETE / INVALID_SPEC), immutable approved
baselines, and human-gated promotion. Loopback-only, GET/HEAD only, no
credentials, no telemetry.

Repo: https://github.com/Mohamedhazeem/ContractGuard

@NousResearch
```

**Character count:** ~880 (X allows 280 for free accounts — use the long-form
post below if you hit the limit, or trim to the first four lines).

## Trimmed version (under 280 characters)

```
HTTP 200 is not proof your API is correct.

ContractGuard is a Hermes plugin that validates requests and live responses
against your OpenAPI contract — before the request is sent, and after.

Repo: https://github.com/Mohamedhazeem/ContractGuard

@NousResearch
```

## Shot notes for the video

Your video is already cut. These are the notes for the **caption** so the post
and the video tell the same story:

| Shot | On-screen | Caption line it matches |
|---:|---|---|
| 0:00 | Terminal: `{"price":"49.99"}`, HTTP 200 | "HTTP 200 is not proof your API is correct." |
| 0:16 | `contractguard_inspect` → `VALID`, 3 ops, SHA-256 | "the contract, read and hashed" |
| 0:25 | `contractguard_register` → candidate baseline | "the target, pinned" |
| 0:28 | `contractguard_validate_request` → `FAIL`, `request_sent: false` | "rejected before dispatch" |
| 0:42 | `contractguard_test` → `FAIL`, `status 200`, `$.price expected number, actual string` | "the same endpoint, HTTP 200, still a contract violation" |
| 0:58 | re-run → `PASS`, same hash | "same check, same spec hash, after the fix: PASS" |
| 1:14 | `contractguard_history` → receipts | "every run leaves a receipt" |
| 1:22 | Title card | "ContractGuard — evidence before you ship." |

### What the caption must communicate

The post text and the video should together answer, in this order:

1. **The problem** — HTTP 200 hides a schema violation. (First line, and the
   first shot.)
2. **The proof** — the tool says `FAIL` on `$.price` even though the status is
   200. This is the whole argument; do not bury it.
3. **The safety** — the bad request was never sent (`request_sent: false`).
   Judges score reliability; this is the most reassuring line you can give.
4. **The closed loop** — same check, same spec hash, `PASS` after the fix.
5. **The trust model** — deterministic verdicts, human-gated promotion,
   loopback-only, no telemetry.

### Do not claim

- "Guaranteed compatibility" or "blocks every breaking change" — the diff is a
  bounded ruleset and reports `unclassified` rather than guessing.
- "Works with any API" — live targets are loopback-only in this release, and
  that is stated in the entry's `known_issues`.
- Any comparison implying the existing validators (Wiretap, Schemathesis) lack
  features. They don't. Position the workflow, not a strawman.

### Hashtags

Keep it to one or none. `#HermesAgent` is optional; the `@NousResearch` tag is
the part that counts. Do not add a hashtag wall — it reads as spam on X and
costs you nothing to skip.

## After posting

Reply to your own post with the plugin page once it exists:

```
Catalog page: https://hermes-agent.nousresearch.com/docs/plugins/contractguard
```

Then submit the form with both links:

- PR:   https://github.com/NousResearch/hermes-agent/pull/153918
- Video: your X post URL
- Form: http://form.typeform.com/to/FwJLvOln

The announcement says the form can be submitted **as soon as the PR is open**,
so you can submit now and update the video link if you repost.
