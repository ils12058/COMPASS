"""Shared Exit Interview error base, independent of service/crypto imports."""


class ExitInterviewError(RuntimeError):
    pass


class InvalidExitInterviewInput(ExitInterviewError):
    pass
