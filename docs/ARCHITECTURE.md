# Architecture

Describe runtime boundaries and the data they own. See [current state](CURRENT_STATE.md) for evidence and [module map](MODULE_MAP.md) for entry points.

- **Configuration** — The YAML scene defines visual effects, clocks, a music brief, environmental settings and the budget.
- **Production state** — The SQLite project store records immutable asset versions, creative review decisions, request fingerprints, spending reservations and provider usage. Media and project databases live outside Git.
- **Providers** — Local and mock adapters share a contract with the OpenAI, Stability AI and ElevenLabs adapters. Billing authorization and cache handling sit in the project store. Local procedural generation produces demonstration artwork and musical candidates.
- **Rendering** — The compositor animates a still and optional reviewed layers. The audio engine renders and mixes periodic stereo stems. FFmpeg accepts streamed frames and muxes the mix.
- **Verification** — QC reads the encoded media, compares seam and neighboring frames and samples, and writes diagnostics. Human viewing and listening gate publication.
- **Development context** — Git carries task records, decisions, guidance and source. Graphify builds a disposable local index. Each worktree can refresh its own copy.

The production path is approved art and music → audiovisual preview → preview approval → full render and QC. The demo path provides original procedural media for local evaluation.
