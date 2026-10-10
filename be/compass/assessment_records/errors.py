class AssessmentRecordError(RuntimeError):
    pass


class AssessmentRecordAccessDenied(AssessmentRecordError):
    pass


class AssessmentRecordNotFound(AssessmentRecordError):
    pass


class InvalidAssessmentRecordInput(AssessmentRecordError):
    pass


class AssessmentRecordConflict(AssessmentRecordError):
    pass
