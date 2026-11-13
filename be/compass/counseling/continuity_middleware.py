"""Apply no-store even to authentication, CSRF, validation and concealed denials."""


class ContinuityNoStoreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        prefixes = (
            "/api/v1/counseling/continuity-grants",
            "/api/v1/counseling/continuity",
            "/api/v1/counseling/cases",
        )
        if any(
            request.path == prefix or request.path.startswith(prefix + "/") for prefix in prefixes
        ):
            response["Cache-Control"] = "private, no-store"
            response["Pragma"] = "no-cache"
        return response
