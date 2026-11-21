"""Restrictive browser policies for JSON API responses, including the host root error."""

from django.http import HttpRequest, HttpResponse

JSON_CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'"

# Permissions Policy has no wildcard directive for denying every feature. Enumerate browser
# features explicitly; JSON has no reason to use any of them. Unknown directives are ignored by
# browsers that do not implement them. Keep this list current as the platform adds features.
DENIED_BROWSER_FEATURES = (
    "accelerometer",
    "ambient-light-sensor",
    "aria-notify",
    "attribution-reporting",
    "autoplay",
    "battery",
    "bluetooth",
    "browsing-topics",
    "camera",
    "captured-surface-control",
    "ch-device-memory",
    "ch-downlink",
    "ch-dpr",
    "ch-ect",
    "ch-prefers-color-scheme",
    "ch-prefers-reduced-motion",
    "ch-prefers-reduced-transparency",
    "ch-rtt",
    "ch-save-data",
    "ch-ua",
    "ch-ua-arch",
    "ch-ua-bitness",
    "ch-ua-form-factors",
    "ch-ua-full-version",
    "ch-ua-full-version-list",
    "ch-ua-high-entropy-values",
    "ch-ua-mobile",
    "ch-ua-model",
    "ch-ua-platform",
    "ch-ua-platform-version",
    "ch-ua-wow64",
    "ch-viewport-height",
    "ch-viewport-width",
    "ch-width",
    "clipboard-read",
    "clipboard-write",
    "compute-pressure",
    "cross-origin-isolated",
    "deferred-fetch",
    "deferred-fetch-minimal",
    "display-capture",
    "digital-credentials-get",
    "document-domain",
    "encrypted-media",
    "fullscreen",
    "gamepad",
    "geolocation",
    "gyroscope",
    "hid",
    "identity-credentials-get",
    "idle-detection",
    "interest-cohort",
    "join-ad-interest-group",
    "keyboard-map",
    "language-detector",
    "language-model",
    "local-fonts",
    "local-network",
    "local-network-access",
    "loopback-network",
    "magnetometer",
    "microphone",
    "midi",
    "on-device-speech-recognition",
    "otp-credentials",
    "payment",
    "picture-in-picture",
    "private-aggregation",
    "private-state-token-issuance",
    "private-state-token-redemption",
    "publickey-credentials-create",
    "publickey-credentials-get",
    "rewriter",
    "run-ad-auction",
    "screen-wake-lock",
    "serial",
    "shared-storage",
    "shared-storage-select-url",
    "speaker-selection",
    "storage-access",
    "summarizer",
    "sync-xhr",
    "translator",
    "unload",
    "usb",
    "web-share",
    "window-management",
    "writer",
    "xr-spatial-tracking",
)
JSON_PERMISSIONS_POLICY = ", ".join(f"{feature}=()" for feature in DENIED_BROWSER_FEATURES)


class JsonSecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        is_json = content_type == "application/json" or (
            content_type.startswith("application/") and content_type.endswith("+json")
        )
        # The API host's root returns the existing JSON 404 envelope and is the URL used by
        # header scanners. Protect it as well, while leaving administrative and HTML views alone.
        is_api_path = request.path_info == "/" or request.path_info.startswith("/api/v1/")
        if is_api_path and is_json:
            response["Content-Security-Policy"] = JSON_CONTENT_SECURITY_POLICY
            response["Permissions-Policy"] = JSON_PERMISSIONS_POLICY
        return response
