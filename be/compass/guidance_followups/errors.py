class FollowUpError(RuntimeError):
    pass


class FollowUpNotFound(FollowUpError):
    pass


class FollowUpPermissionDenied(FollowUpError):
    pass


class FollowUpInvalid(FollowUpError):
    pass


class FollowUpConflict(FollowUpError):
    pass


class FollowUpContentUnavailable(FollowUpError):
    pass
