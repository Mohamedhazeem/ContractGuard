# ADR-002: Store immutable JSON baselines with SHA-256 in SQLite

- **Status:** Accepted
- **Date:** 2026-11-10
- **Deciders:** ContractGuard maintainers
- **Related:** [Product specification, §15](../plan/ContractGuard_Project_Spec.md),
  [Implementation slice 2](../plan/ContractGuard_Implementation.md),
  [ADR-003](003-synchronous-execution.md)

## Context

A baseline is the human-approved reference contract used to decide whether a
candidate change is breaking. Its integrity is the foundation of every diff
result. If the reference can change without an explicit approval event, the
product's central claim ("this change is breaking relative to what you approved")
becomes unfalsifiable.

The obvious implementation — store the path to `openapi.yaml` — fails in several
ways:

- The file is mutable. Editing it changes the baseline silently, which is
  exactly the event we are supposed to review.
- The file may be moved, deleted, or replaced between diff and promotion
  (time-of-check/time-of-use).
- A diff run tomorrow would use different bytes than the evidence recorded
  yesterday, so the evidence receipt is not reproducible.
- Git refs are not always available (the user may not have committed), and a
  branch ref is mutable too.
- Storing only a hash without the document makes historical diffs impossible
  once the file changes.

The baseline must be **self-contained, content-addressed, immutable, and
transactionally promotable**.

## Decision

Store the complete normalized OpenAPI document as JSON together with its
SHA-256 digest in SQLite. The file path is never the identity of a baseline.

Specifically:

1. **Normalize before hashing.** Parse JSON/YAML into a Python mapping, then
   serialize canonically:
   `json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
   encoded as UTF-8. Arrays are not globally sorted; ordering can be semantic.
2. **Hash the canonical bytes.** `sha256` is lowercase hexadecimal, 64
   characters. The same logical document yields the same digest across machines.
3. **Persist a new row per promotion** in `baselines`, including
   `baseline_id`, `service_id`, `version_label`, `spec_sha256`, `spec_json`,
   `parent_baseline_id`, `promoted_at`, and `is_current`.
4. **Never update or delete a promoted baseline.** Promotion inserts a new row
   and flips the current flag inside one transaction. A partial unique index
   enforces at most one `is_current = 1` row per service.
5. **Compare-and-swap promotion.** The promotion transaction re-reads and
   re-hashes the candidate, verifies the caller-supplied `candidate_sha256`
   matches, and verifies the expected current baseline ID has not changed. A
   stale or concurrent promotion is rejected, not merged.
6. **Diff reads the stored JSON**, not the original path. The candidate is read
   from disk, validated, normalized, and hashed in the same request.
7. **Promotion requires explicit human approval** through the `pre_tool_call`
   hook. No register, test, or diff path promotes implicitly.

The `services` table may still record a convenience `spec_path` for the user's
workflow, but no correctness decision may depend on that path. The path is
provenance, not authority.

## Consequences

### Positive

- Editing `openapi.yaml` on disk cannot alter an approved baseline.
- Diff results and evidence receipts remain reproducible after the working tree
  changes.
- Historical baselines support audit, rollback, and version comparison without
  relying on git.
- Content addressing makes duplicate detection and equality checks trivial.
- Transactional compare-and-swap prevents a lost update when two sessions act
  concurrently.

### Negative

- The database grows with each promoted version. With a 2 MiB spec cap and a
  bounded history, growth is acceptable; retention policy must still be defined.
- Specs can contain internal hostnames, comments, or example secrets. Baseline
  JSON is stored locally in Hermes plugin storage, never uploaded, and must not
  be logged or returned in full by history tools.
- Canonicalization must be consistent across parse paths. JSON and YAML inputs
  that are semantically identical must hash identically; tests must pin this.
- Hash stability is a compatibility surface. Changing normalization requires a
  new hash scheme/version and a migration, not a silent re-hash.
- Duplicate content still creates a new row unless we explicitly detect it. The
  promotion path should reject unchanged candidates or record them as a no-op.

### Storage rules

- Use `plugin_db("contractguard")`, never a database file inside the install
  directory.
- Foreign keys are enforced. Writes occur in short transactions.
- A storage failure must preserve existing rows and surface `STORAGE_ERROR`; it
  must never fall back to recreating the database.
- History queries return metadata and hashes, not the full `spec_json`.

## Alternatives considered

### Store only the file path

Rejected for the reasons in the Context section. This is the failure mode the
ADR exists to prevent.

### Store a git commit SHA or branch ref

Rejected. It couples the plugin to a VCS, fails for uncommitted specifications,
and a branch ref remains mutable. A commit SHA is immutable but does not
guarantee the file still exists in a shallow clone or that the working tree
matches it.

### Store only the SHA-256 hash

Rejected. It proves integrity but not availability. Historical diffs would need
the original bytes, which may no longer exist.

### Content-addressed blob store on disk

Rejected for the MVP. It adds file lifecycle, garbage collection, and atomicity
concerns that SQLite already solves for a document capped at 2 MiB. It may be
revisited if baseline volume grows substantially.

### Hybrid: path plus hash

Rejected as the primary identity. A path plus a hash can detect drift, but it
still cannot reconstruct the approved document after the file is deleted, and it
keeps the path on the correctness path.

## References

- ContractGuard product specification, section 15 (persistence and storage).
- SQLite partial indexes: <https://www.sqlite.org/partialindex.html>
- Python `hashlib` and `json` canonicalization documentation.
- Hermes plugin storage helpers: `plugins.plugin_storage.plugin_data_dir` and
  `plugin_db`.
