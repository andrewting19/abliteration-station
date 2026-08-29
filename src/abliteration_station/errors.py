class LifecycleError(RuntimeError):
    """A provider or lifecycle operation failed."""


class ProviderUnavailable(LifecycleError):
    """A provider is not configured or cannot currently serve the request."""

