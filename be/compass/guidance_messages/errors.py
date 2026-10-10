class GuidanceMessagesError(RuntimeError):
    """Errors retain only bounded structural descriptions, never submitted content."""


class ThreadNotFound(GuidanceMessagesError):
    def __init__(self):
        super().__init__("The requested Guidance thread was not found.")


class MessagesPermissionDenied(GuidanceMessagesError):
    def __init__(self):
        super().__init__("You do not have permission to perform this action.")


class TemplateNotFound(GuidanceMessagesError):
    def __init__(self):
        super().__init__("The requested Message template was not found.")


class InvalidMessageInput(GuidanceMessagesError):
    pass


class MessagesConflict(GuidanceMessagesError):
    pass


class TemplateNameTaken(MessagesConflict):
    def __init__(self):
        super().__init__("A Message template with this name already exists.")


class GuidanceMessageContentUnavailable(GuidanceMessagesError):
    def __init__(self):
        super().__init__("Guidance Message confidential content is unavailable.")
