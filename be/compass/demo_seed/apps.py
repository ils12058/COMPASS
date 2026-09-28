from django.apps import AppConfig


class DemoSeedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "compass.demo_seed"
    label = "demo_seed"
    verbose_name = "COMPASS staging demo dataset tooling"
