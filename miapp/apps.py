from django.apps import AppConfig
from django.conf import settings

class MiappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "miapp"

    def ready(self):
        from . import signals  

       
        if getattr(settings, "AUTO_SYNC_INVENTARIO_ON_START", False):
            try:
                from django.db import connection
                from miapp.utils import sync_inventario_inicial
                
                if connection.introspection.table_names():
                    sync_inventario_inicial()
            except Exception:
                pass
