"""Apply no-store even to authentication, CSRF, validation and concealed denials."""


class ContinuityNoStoreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        prefix = "/api/v1/counseling/continuity-grants"
        if request.path == prefix or request.path.startswith(prefix + "/"):
            response["Cache-Control"] = "private, no-store"
        return response
