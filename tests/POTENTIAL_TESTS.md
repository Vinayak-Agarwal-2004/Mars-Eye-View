# Potential Test Candidates

This registry maps confirmed issues to candidate automated tests. Use this to build out the `tests/` suite.

## High Value Candidates

### 1. Multi-Source Integration Test
- **Source**: [ISSUE-002](../issues/ISSUE-002.md)
- **Goal**: Verify that an event with >1 source actually renders >1 link in the output JSON.
- **Method**: Mock GDELT `LastUpdate.txt` to point to a controlled `mentions.CSV` and `export.CSV` pair. Assert `len(event['sources']) > 1`.

### 2. Deduplication Logic Unit Test
- **Source**: [ISSUE-010](../issues/ISSUE-010.md)
- **Goal**: Ensure distinct events at the same location (e.g. centroid) are NOT dropped.
- **Method**: Feed the `Deduplicator` class two events: same Lat/Lon/Name, different `EventCode`. Assert `output_count == 2`.

### 3. ACLED Pruning Test
- **Source**: [ISSUE-011](../issues/ISSUE-011.md)
- **Goal**: Verify old data is actually removed.
- **Method**: Create a dummy JSON with 1 event from last year and 1 from today. Run `prune_data()`. Assert `count == 1`.

### 4. UI Component Rendering Tests (Frontend)
- **Source**: [ISSUE-007](../issues/ISSUE-007.md)
- **Goal**: Ensure `SufferingLayer.js` functions handle empty inputs gracefully.
- **Method**: Jest/Vitest unit test calling `showDisputePanel({claimants: undefined})` and asserting no crash.

## Test Implementation Roadmap

| Priority | Test Name | Coverage Area | Complexity |
|:---|:---|:---|:---|
| P0 | `test_deduplication.py` | Data Integrity | Low |
| P1 | `test_pruning.py` | Persistence | Low |
| P2 | `test_gdelt_join.py` | Integration | High |
