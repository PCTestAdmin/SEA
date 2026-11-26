# Evidence system (v0.13)

Create a dedicated private directory and add its absolute path as SEA_EVIDENCE_DIR in the MCP server environment. Restart the client. This is separate from SEA_MEMORY_DIR. Disabled by default. The database is unencrypted; reports may contain sensitive measurements. Do not share the directory with other writers.

capture_evidence(path,tool,start_s=0,duration_s=10,confirm=false) runs the selected analyzer and stores the result only with explicit approval. Supported: sense_media, sense_audio, sense_video, investigate_media and inspect_spatial (start_s is time, fixed grid 3). Only authorized media roots, max source 128 MiB, 512 KiB report, 100 records. No raw media is stored. Source basenames are removed from these selected reports. The SHA-256 of the canonical JSON envelope is its ID; the envelope contains source byte hash, size, engine version, parameters and UTC timestamp.

list_evidence lists records; recall_evidence returns the full JSON envelope after checking its digest. The host may export this JSON. verify_evidence checks whether a selected local source has the same bytes and whether the stored report digest matches. It does not rerun analysis or authenticate the creator. Anyone able to modify the database can generate a different report and hash; this is not a digital signature or chain of custody. delete_evidence requires confirm=true and explicit approval; logical deletion only.

The MCP host controls calls; the confirmation flag is not independent authentication. Remove the environment setting to disable access. Results can be sent to the host/model. Image/model outputs are not yet archived by this evidence subsystem.
