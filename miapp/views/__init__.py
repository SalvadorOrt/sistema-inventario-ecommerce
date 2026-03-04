# miapp/views/__init__.py

# 1. Importamos las vistas de Autenticación
from .auth_views import login_view, logout_view, inicio

# 2. Importamos las vistas de Consultas (Kardex, Pedidos, Transferencias)
from .consultas_views import (
    kardex_consulta,
    kardex_detalle,
    transferencias_consulta,
    transferencia_detalle,
    pedidos_consulta,
    pedido_detalle
)

# 3. Helpers
from .helpers import _get_context_base

from .operaciones_views import mov_entrada