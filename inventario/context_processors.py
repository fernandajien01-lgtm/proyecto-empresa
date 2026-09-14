from .models import Carrito


def carrito_items(request):
    if request.user.is_authenticated and request.user.role == "CLIENTE":
        carrito = Carrito.objects.filter(cliente=request.user).first()
        if carrito is not None:
            items = sum(i.cantidad for i in carrito.items.all())
            return {"cart_items": items}
    return {"cart_items": 0}