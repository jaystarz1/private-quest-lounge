# Confirmed live rollback: 2026-08-11 23:35 EDT

This checkpoint preserves the immutable production artifacts loaded when Jay
reported: "Okay, live testing went well" at 2026-08-11 23:35 EDT.

## Artifacts

- `hub-b20750bbac7c39c40466.js`
  - SHA-256: `45452a864472318e121ab26a4030b974bc189476ed873bede6080d7d19a232ec`
- `avatar-jay-real-5a835a8f390a152947dc.glb`
  - SHA-256: `36c0134607c6bddbe011cdb773afec8b4cc8e86d88e4d12a57229f6ae6d608bf`
- `avatar-her-real-2bf393920085d2133587.glb`
  - SHA-256: `44194b1dca745b32c491e6ef0344320fe487fe1e678838c54b5cb2a73d5cb818`
- `avatar-arm-ik.js`
  - SHA-256: `bb5f9fba1cb72ae73dd55af46fe33676d301d54b3c119e4f0df696801f138ecb`

## Scope

The two GLBs are the exact pre-mouth-tag production avatar bytes. Restoring
this checkpoint restores the complete known-good arm state but also restores
the non-moving mouths. Mouth animation must be reintroduced outside the GLB
files so these confirmed avatar bytes remain untouched.
