from .models import Carrito


def carrito_items(request):
    if request.user.is_authenticated and request.user.role == "CLIENTE":
        carrito = Carrito.objects.filter(cliente=request.user).first()
        if carrito is not None:
            items = sum(i.cantidad for i in carrito.items.all())
            return {"cart_items": items}
    return {"cart_items": 0}


def notificaciones_empleado(request):
    if request.user.is_authenticated and request.user.role == "EMPLEADO":
        no_leidas = request.user.notificaciones.filter(leida=False)
        return {
            "notificaciones_no_leidas": no_leidas.count(),
            "notificaciones_recientes": no_leidas[:5],
        }
    return {"notificaciones_no_leidas": 0, "notificaciones_recientes": []}