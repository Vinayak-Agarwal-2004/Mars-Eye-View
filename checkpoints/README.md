# Checkpoints

JSON files storing pipeline state for resumption and test isolation.

## Purpose

CheckpointManager (server/app/services/checkpoint.py) persists last_timestamp, processed_count, and optional metadata. Used by FirehoseService after each fetch cycle so the pipeline can resume from the last successful run. Orchestration and monitoring can read state to report progress.

## Files

- **pipeline_state.json** – Production checkpoint. Written by FirehoseService after GDELT fetch. Contains last_timestamp, processed_count, metadata (export_url, features_count).

- **test_integration_state.json** – Integration tests use a dedicated checkpoint path to avoid overwriting production state.

- **test_pipeline_state.json** – E2E or pipeline tests use a separate checkpoint for isolation.
