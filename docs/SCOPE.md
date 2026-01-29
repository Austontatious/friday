# FRIDAY Scope

## Product Goal
A private-first, modular personal assistant that can run locally (single machine) or distributed (multi-container), with graceful degradation from full multimodal to text-only.

## In Scope (MVP → SOTA)
### Baseline (must always work)
- Text chat
- Tool calling (structured JSON schema)
- Session + identity resolution
- Tiered memory (ephemeral + persisted)

### Add-on modalities (feature-flagged)
- STT (speech-to-text)
- TTS (text-to-speech)
- Vision (image understanding)
- Gesture (hand tracking / 3D control)
- Avatar (real-time render, “holographic monochrome” aesthetic)

## Out of Scope (for now)
- Full “AI girlfriend” emotional manipulation
- Heavy social roleplay productization
- Payments, accounts, multi-tenant enterprise auth (can be added later)

## Non-negotiables
- Safe no-op defaults: if a service is off, the system still runs.
- Long tasks async or streamed.
- No hard-coded machine paths.
- Clear operator runbook.
