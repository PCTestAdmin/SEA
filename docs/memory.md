# Perception memory (v0.8)

SEA can store numeric audio and sensor summaries across sessions, without storing raw recordings or source paths. This feature is disabled by default and does not retain ordinary tool calls or conversations.

## Enable

Create a dedicated existing private directory, separate from shared media folders. Add `SEA_MEMORY_DIR` with its absolute path to the SEA server's env object in your MCP configuration (next to SEA_MEDIA_ROOTS). Restart the client. Do not give other users write access to this directory. The guided setup does not configure memory automatically; it is a manual opt-in.

SEA creates sea-memory.sqlite3 on the first save. Each record contains an ID, UTC creation time, user label, measurement kind, engine version and numeric summary. Sensor channel names are retained; labels and channel names can be sensitive. No source file path/name, raw samples, frames or raw CSV rows are stored. SQLite is not encrypted by SEA. Use OS account permissions or encrypted storage if needed; backups and disk remnants may persist after deletion. Local history is shared by clients configured to the same memory directory. Retrieved records can be transmitted by the MCP host to its model provider.

## Tools

- remember_audio(path,label,start_s=0,duration_s=15): save a new measurement (0.25–30 s).
- remember_signals(path,label,time_column,channels): save a fresh numeric CSV summary.
- list_perception_memory(limit=20): list saved IDs and labels.
- recall_perception(record_id): retrieve historical evidence.
- compare_perception(id_a,id_b): report B minus A numeric deltas; same kind and engine version required. Audio durations and sample rates must match, sensor channel names must match. Units and recording conditions must be comparable.
- forget_perception(record_id,confirm=false): delete one record after explicit user approval; confirm=true is required.

Ask the agent to save only after you approve the label and source, and to delete only after you approve the selected record. This approval instruction is not an independent authentication boundary; the MCP host controls tool calls. The directory setting is the primary opt-in. To disable, remove SEA_MEMORY_DIR and restart. This does not erase existing records. To remove the whole database, close all SEA servers and delete the database and any backups yourself.

Storage is limited to 100 records, with no automatic eviction, and 128 KiB JSON per record. Comparisons are historical numeric differences, not automatic diagnosis, causal inference, source matching or semantic memory. See [tests](../tests/test_memory.py).
