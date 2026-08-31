# Extending Abliteration Station

The controller is provider-neutral. The included Vast and Qwen3.8 files are the
only fully tested profile in version 0.1.

## Add a provider

Implement a Python class with these methods:

- `doctor() -> list[str]`
- `ensure() -> Route`
- `stop() -> None`
- `status() -> dict`

The constructor receives the provider configuration object. Set its adapter in
the configuration as `module.path:ClassName`:

```json
{
  "provider_order": ["my-provider", "vast"],
  "providers": {
    "my-provider": {
      "adapter": "my_package.provider:MyProvider"
    }
  }
}
```

The adapter package must be available on the controller Python path. The core
controller does not need a provider-specific edit. Add failure, cleanup,
concurrent-start, and cost-cap tests before you claim support.

## Add a model profile

The controller and Pi registration read these model fields from configuration:

- `id`
- `display_name`
- `context_size`
- `quant_prefix`
- `temperature`
- `reasoning_effort`

Provider deployment assets stay provider-specific. A Vast model fork must also
replace and pin the artifact and runtime values in:

- `scripts/vast/portable-manifest.env`
- `scripts/vast/runtime.env`
- `scripts/vast/run-qwen38-cloud.sh`
- the synthetic acceptance workload and quality gates

Do not reuse Qwen3.8 performance claims for another model. Publish its model
license, exact hashes, context behavior, tool-loop result, quality evidence,
and long-context speed result.

## Acceptance boundary

An adapter or profile is experimental until it passes local CI, clean install,
private routing, cancellation, idle stop and wake, tool use, the declared
context gate, and its documented performance floor.
