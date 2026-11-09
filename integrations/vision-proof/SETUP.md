# Vision-model proof workflow — DISABLED by default (optional experiment)

Status: **placeholder with intent**. PDF section 6.2 describes the
screenshot -> vision model -> evaluator pipeline. The dossier
qualifies it (2.3, D-017): a model description is NOT independent
proof; it is at best a third evidence class ("submitted + described"),
never machine-checked.

This is why `dhriti proof` has no screenshot subcommand in v1: it
raises a clear error pointing here instead of silently faking a
capability that needs YOUR API key or YOUR local model download.

## What the design expects (when you enable it)

```
1. user completes task (or claims to)
2. screenshot of IDE/terminal/browser evidence
3. vision model (Gemini / GPT-4V / local Qwen2.5-VL) returns a
   STRUCTURED DESCRIPTION only:
     {screen_type, visible_content, text_extracted,
      application, file_name, task_relevance_hint}
4. Dhriti's evaluator compares the description against the contract's
   evidence spec -> accept/reject
5. screenshot deleted immediately; description deleted after verdict
```

Two separate models, two separate jobs; neither is a single point of
failure, and neither is on the enforcement critical path (D-014).

## Manual steps to enable (when you decide to)

1. Choose a provider and get an API key, or download a local
   vision model (e.g. Qwen2.5-VL via Ollama/llama.cpp).
2. Add to `dhriti.config.json`:

```json
"vision_proof": {
  "enabled": true,
  "provider": "local-qwen",
  "endpoint": "http://127.0.0.1:11434/api/generate",
  "api_key_env": "DHRITI_VISION_KEY",
  "delete_screenshot_after": "immediately"
}
```

3. Implement the adapter against this contract: it MUST return the
   structured description above; Dhriti's evaluator consumes only
   that JSON. (A stub module can be added to
   `dhriti/adapters/observation/` following the same Adapter base.)
4. Record evidence class as SUBMITTED (description), never
   MACHINE_CHECKED — the vision model's word is a claim, not a check.

## Hard rules that stay regardless

- Screenshots are deleted immediately after description; only the
  structured description is stored, and only until the verdict.
- The verdict influence is capped: vision-assisted proof can close a
  session, but the aftermath report labels its evidence class
  honestly.
- Provider lock-in is forbidden by design (D-014): swap providers by
  config, never by rewriting the evaluator.
