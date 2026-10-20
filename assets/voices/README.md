# Reference voices

Reference audio for the Chatterbox TTS engine.

| File | What it is |
|---|---|
| `p241_vits_source.wav` | Raw render of VCTK speaker p241 from Coqui VITS (`tts_models/en/vctk/vits`), 22.05 kHz. |
| `ref_p241_clean.wav` | `p241_vits_source.wav` pitch-flattened with Praat PSOLA (Stylize, 0.5 semitones). |

`ref_p241_clean.wav` has md5 `84d201496b4ba6601583dec45e1ee29c`. Rebuild it with:

    python scripts/build_reference.py stylize assets/voices/p241_vits_source.wav /tmp/ref.wav

This needs `praat-parselmouth` and is byte-reproducible. Re-rendering the source
(`build_reference.py vits`) is not: VITS samples noise, so the source is checked in.

## Attribution

- **VCTK Corpus 0.92**, licensed **CC BY 4.0**. Yamagishi, Veaux and MacDonald,
  CSTR, University of Edinburgh, 2019. The VITS model was trained on it.
- **Coqui `tts_models/en/vctk/vits`**, Apache-2.0 per the coqui-tts `.models.json`.
- The sentences synthesised for the source were written for this project.
  The XTTS v2 licence (CPML) does not apply to these files.
