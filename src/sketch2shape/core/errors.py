"""User-facing error types. Anything else that escapes a stage is wrapped into PipelineError."""


class PipelineError(RuntimeError):
    """An error whose message is safe to show in the UI."""

    def __init__(self, message: str, *, stage: str | None = None, detail: str | None = None):
        super().__init__(message)
        self.stage, self.detail = stage, detail


class NoCudaError(PipelineError):
    pass


class OOMError(PipelineError):
    pass


class BackendUnavailable(PipelineError):
    pass


class Cancelled(PipelineError):
    pass
