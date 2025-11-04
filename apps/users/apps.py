from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'

    def ready(self):
        # Aquí podrías importar señales si las usas (ejemplo: from . import signals)
        # Pero NUNCA importar modelos aquí directamente.
        pass
