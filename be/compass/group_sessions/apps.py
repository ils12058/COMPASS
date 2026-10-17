"""Group Sessions & Events application config."""

from django.apps import AppConfig


class GroupSessionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "compass.group_sessions"
    label = "group_sessions"
