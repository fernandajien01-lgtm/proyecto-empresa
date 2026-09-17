from django.db.models import Sum

from .models import CarritoItem, Notificacion


def carrito_count(request):
    count = 0
    if request.user.is_authenticated and request.user.role == "CLIENTE":
        count = CarritoItem.objects.filter(usuario=request.user).aggregate(
            total=Sum("cantidad")
        )["total"] or 0
    return {"carrito_count": count}


def notificaciones_empleado(request):
    if request.user.is_authenticated and request.user.role in {"EMPLEADO", "EMPRESA"}:
        no_leidas = request.user.notificaciones.filter(leida=False)
        return {
            "notificaciones_no_leidas": no_leidas.count(),
            "notificaciones_recientes": no_leidas[:5],
        }
    return {"notificaciones_no_leidas": 0, "notificaciones_recientes": []}