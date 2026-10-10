"""Standalone realtime WebSocket service (ADR-100).

This package never imports Django, the ORM, COMPASS domain models, or confidential-content
encryption code. It authenticates sockets only with one-time tickets that the Django HTTP
application mints into Redis, and it forwards only content-free hints published to Redis.
"""
