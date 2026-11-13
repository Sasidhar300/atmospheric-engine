# Current state

Use these status labels when recording changes. **Implemented** means the code exists. **Tested** means an observed command supports the claim. **Approved** requires a recorded human decision. **Incomplete** marks work that still needs verification or approval. **Planned** marks future work.

| Area | Status and evidence |
| --- | --- |
| Local renderer and QC | Implemented and tested on Apple Silicon. The 90-second demo decoded to 2700 frames at 1920×1080 and 30 fps with 48 kHz stereo. Eight automated QC checks passed. |
| Audio | Implemented and tested in the demo. Music, rain, wind and the stereo mix were exported as separate WAVs. |
| Pilot | Human approval is pending. Local evidence lives in `outputs/qc_report.json` and `outputs/seam_preview.mp4`. Reproduce with `.venv/bin/python -m atmosphere demo --duration 90`. |
| Paid providers | Implemented and tested with mocks. Live execution remains unverified. The local run used US$0. |
| Creative approval and spending | Tested offline for preview approval, budget reservation, cache reuse and failed requests. |
| Cross-client handoff | See the [active handoff](HANDOFF.md) for verified local behavior and client-specific steps that remain. |
| Publication | Planned. Requires approved artwork, score and preview, and explicit publication approval. |
