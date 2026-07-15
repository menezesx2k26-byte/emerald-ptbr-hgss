# Translation shards v1.3

These four compressed patches are the completed output of the deterministic
four-shard PT-BR translation run. They are stored here so rebuilding the ROM
does not depend on expiring GitHub Actions artifacts or rerunning the CPU-heavy
machine-translation model.

- Base source: `lucmsilva651/esmeralda-ptbr@16899178c5d9b198b961c3e38389ccccbdff7836`
- Model: `Helsinki-NLP/opus-mt-tc-big-en-pt`
- Shards: `0..3` of `4`
- Move names and move descriptions: deliberately excluded
- Post-processing: safety sanitizer, reviewed v1.3.1 fixes, token repair and
  charmap validation

The adjacent JSON files are the original per-shard reports. The workflow
decompresses and applies the patches in filename order.
