class GuidanceMessagesError(RuntimeError):
    """Errors retain only bounded structural descriptions, never submitted content."""


class ThreadNotFound(GuidanceMessagesError):
    def __init__(self):
        super().__init__("The requested Guidance thread was not found.")


class MessagesPermissionDenied(GuidanceMessagesError):
    def __init__(self):
        super().__init__("You do not have permission to perform this action.")


class InvalidMessageInput(GuidanceMessagesError):
    pass


class MessagesConflict(GuidanceMessagesError):
    pass


class GuidanceMessageContentUnavailable(GuidanceMessagesError):
    def __init__(self):
        super().__init__("Guidance Message confidential content is unavailable.")
