# System Learnings & Root Cause Analysis

This document serves as a knowledge base, capturing the "Why" behind confirmed defects to prevent regression.

## Learning Log

### 1. GDELT v2 Mentions Data Structure (Source: ISSUE-002)
- **Observation**: GDELT Events (`export.CSV`) contain only the *citation* URL, not the full list of sources.
- **Root Cause**: Source coverage requires joining the `mentions.CSV` stream.
- **Takeaway**: Any feature requiring "All Sources" must implement a stream-join architecture (Events + Mentions) keyed by `GlobalEventID`. relying on the Event stream alone is insufficient.

### 2. Side Panel Update Logic (Source: ISSUE-016)
- **Observation**: Switching Admin regions causes blank white screens.
- **Root Cause**: The UI state manager invalidates the DOM before new data is fully fetched, leaving the container empty if the fetch lags or fails.
- **Takeaway**: UI updates must be optimistic or use a "skeleton loader" state rather than clearing the DOM immediately.

### 3. Timestamp Collision in GDELT (Source: ISSUE-010)
- **Observation**: High-intensity conflicts in single locations (e.g., Gaza, Ukraine) get dropped.
- **Root Cause**: Deduplicators using `Name + Lat/Lon` signatures are too aggressive for GDELT, which maps multiple distinct events to the same centroid.
- **Takeaway**: Deduplication must include `EventCode` or `TimeAdded` to distinguish concurrent events in the same location.
