## REMOVED Requirements

### Requirement: Runtime prompt files
**Reason**: Provider-neutral prompt loading moves to `prompt-and-generation`.
**Migration**: Use `ai.prompt_loader.PromptLoader`.

### Requirement: Prompt composition
**Reason**: Prompt composition is now specified without a Gemini dependency.
**Migration**: Use the equivalent requirement in `prompt-and-generation`.

### Requirement: Persona overlays provide distinctive human behavior guidance
**Reason**: Persona behavior no longer names a provider.
**Migration**: Use `Existing conversational prompt behavior` in `prompt-and-generation`.

### Requirement: Topic loading
**Reason**: Topic loading is provider-neutral.
**Migration**: Use `Prompt composition and topics` in `prompt-and-generation`.

### Requirement: Topic key caching
**Reason**: Topic caching is provider-neutral.
**Migration**: Use `Prompt composition and topics` in `prompt-and-generation`.

### Requirement: Gemini reply generation
**Reason**: Gemini is removed.
**Migration**: Use `Provider-neutral generation interface` and `Strict OpenRouter requests`.

### Requirement: Gemini resilience
**Reason**: Gemini is removed.
**Migration**: Use `OpenRouter retries and errors` and `Model fallback`.

### Requirement: Safe proxy reporting
**Reason**: Proxy reporting belongs to provider-neutral observability.
**Migration**: Use `Safe provider observability`.

### Requirement: Important service start-topic prompt behavior
**Reason**: Prompt behavior no longer names a provider capability.
**Migration**: Use `Existing conversational prompt behavior`.

### Requirement: Important service reply prompt behavior
**Reason**: Prompt behavior no longer names a provider capability.
**Migration**: Use `Existing conversational prompt behavior`.

### Requirement: Ordinary prompt behavior remains non-promotional
**Reason**: Prompt behavior no longer names a provider capability.
**Migration**: Use `Existing conversational prompt behavior`.

### Requirement: Gemini input redaction
**Reason**: Gemini is removed.
**Migration**: Use `Generation input redaction`.

### Requirement: Gemini output safety validation
**Reason**: Gemini is removed.
**Migration**: Use `Generation output safety`.
