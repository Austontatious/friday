# FRIDAY Service Contracts (Stubbed)

These endpoints are inert stubs for Phase 1.7. They return 200 with a disabled message unless explicitly enabled.

## Speech-to-Text (STT)
- Endpoint: `POST /api/stt`
- Response (disabled): `{ "status": "disabled", "message": "[STT disabled] Set FRIDAY_STT_ENABLED=1" }`

## Text-to-Speech (TTS)
- Endpoint: `POST /api/tts`
- Response (disabled): `{ "status": "disabled", "message": "[TTS disabled] Set FRIDAY_TTS_ENABLED=1" }`

## Vision
- Endpoint: `POST /api/vision`
- Response (disabled): `{ "status": "disabled", "message": "[Vision disabled] Set FRIDAY_VISION_ENABLED=1" }`

## Avatar
- Endpoint: `POST /api/avatar`
- Response (disabled): `{ "status": "disabled", "message": "[Avatar disabled] Set FRIDAY_AVATAR_ENABLED=1" }`

## Error Envelope (when enabled but unimplemented)
```
{
  "error": {
    "code": "not_implemented",
    "message": "Service enabled but not implemented",
    "detail": "<service>",
    "retryable": false
  }
}
```
