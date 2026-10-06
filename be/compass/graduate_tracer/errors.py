"""Graduate Tracer domain error bases; no sensitive context."""


class GraduateTracerError(RuntimeError):
    pass


class InvalidGraduateTracerInput(GraduateTracerError):
    pass
