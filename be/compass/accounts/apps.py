from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "compass.accounts"
    label = "accounts"
    verbose_name = "COMPASS accounts"

    def ready(self):
        from django.db.models.signals import pre_migrate

        # Accounts is the root of the migration graph; register the reset-only baseline guard.
        from compass.common.canonical_baseline import refuse_pre_canonical_migrate

        pre_migrate.connect(
            refuse_pre_canonical_migrate, sender=self, dispatch_uid="compass.canonical_baseline"
        )
