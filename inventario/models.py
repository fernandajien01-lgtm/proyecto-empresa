from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ("EMPRESA", "Empresa"),
        ("EMPLEADO", "Empleado"),
        ("CLIENTE", "Cliente"),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="CLIENTE")
    empresa = models.ForeignKey(
        "Empresa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="empleados",
    )
    profile_image = models.ImageField(upload_to="profiles/%Y/%m/%d/", blank=True, null=True)
    cedula = models.CharField("Cédula", max_length=20, unique=True, null=True, blank=True)
    telefono = models.CharField("Teléfono", max_length=20, blank=True, default="")
    residencia = models.CharField("Residencia", max_length=255, blank=True, default="")
    fecha_nacimiento = models.DateField("Fecha de nacimiento", null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"


class Empresa(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    rif = models.CharField(max_length=50, blank=True, default="")
    direccion = models.CharField(max_length=255, blank=True)
    instagram = models.CharField(max_length=255, blank=True, default="")
    pagina_web = models.URLField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre


DEFAULT_CATEGORIAS = [
    "Comida",
    "Ropa",
    "Joyas",
    "Hogar",
    "Vehículos",
    "Juguetes",
    "Cursos",
    "Cuidado personal",
    "Electrónica",
    "Accesorios",
]


def ensure_default_categorias():
    for nombre in DEFAULT_CATEGORIAS:
        Categoria.objects.get_or_create(nombre=nombre)


class Proveedor(models.Model):
    nombre_negocio = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.nombre_negocio


class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    imagen = models.ImageField(upload_to="productos/%Y/%m/%d/", blank=True, null=True)
    codigo_sku = models.CharField(max_length=100, unique=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="productos")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="productos")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="productos")
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_stock = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=0)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.codigo_sku})"

    @property
    def bajo_stock(self):
        return self.cantidad_stock <= self.stock_minimo


class Movimiento(models.Model):
    TIPO_ENTRADA = "ENTRADA"
    TIPO_SALIDA = "SALIDA"
    TIPO_CHOICES = (
        (TIPO_ENTRADA, "Entrada"),
        (TIPO_SALIDA, "Salida"),
    )

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="movimientos")
    tipo_movimiento = models.CharField(max_length=20, choices=TIPO_CHOICES)
    cantidad = models.PositiveIntegerField()
    fecha_hora = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimientos")
    nota = models.TextField(blank=True)

    def __str__(self):
        return f"{self.producto.nombre} - {self.tipo_movimiento} ({self.cantidad})"


class SolicitudEmpleado(models.Model):
    PENDIENTE = "PENDIENTE"
    ACEPTADA = "ACEPTADA"
    RECHAZADA = "RECHAZADA"
    CANCELADA = "CANCELADA"
    ESTADO_CHOICES = (
        (PENDIENTE, "Pendiente"),
        (ACEPTADA, "Aceptada"),
        (RECHAZADA, "Rechazada"),
        (CANCELADA, "Cancelada"),
    )

    empleado = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="solicitudes")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="solicitudes_empleado")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=PENDIENTE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("empleado", "empresa")

    def __str__(self):
        return f"{self.empleado.username} -> {self.empresa.nombre} ({self.estado})"


class Sugerencia(models.Model):
    empleado = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="sugerencias")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="sugerencias")
    titulo = models.CharField(max_length=200)
    contenido = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.titulo} - {self.empleado.username}"


class Resena(models.Model):
    CALIFICACION_CHOICES = [(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")]

    producto = models.ForeignKey("Producto", on_delete=models.CASCADE, related_name="reseñas")
    autor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="reseñas", null=True, blank=True)
    nombre_anonimo = models.CharField(max_length=120, blank=True)
    calificacion = models.PositiveSmallIntegerField(choices=CALIFICACION_CHOICES, default=5)
    contenido = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        if self.autor:
            return f"Reseña de {self.autor.username} sobre {self.producto.nombre}"
        return f"Reseña anónima sobre {self.producto.nombre}"

    def puede_editar(self):
        return timezone.now() - self.fecha_creacion < timezone.timedelta(hours=24)

    def clean(self):
        if self.autor is None and not self.nombre_anonimo:
            raise ValidationError("Si el autor es anónimo, debe indicar un nombre público.")


class ReaccionResena(models.Model):
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"
    TIPO_CHOICES = (
        (LIKE, "Like"),
        (DISLIKE, "Dislike"),
    )

    resena = models.ForeignKey(Resena, on_delete=models.CASCADE, related_name="reacciones")
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="reacciones_resena")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    class Meta:
        unique_together = ("resena", "usuario")

    def __str__(self):
        return f"{self.usuario.username} {self.tipo} a reseña {self.resena_id}"


class ReaccionProducto(models.Model):
    LIKE = "LIKE"
    TIPO_CHOICES = ((LIKE, "Like"),)

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="reacciones_producto")
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="reacciones_producto")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=LIKE)

    class Meta:
        unique_together = ("producto", "usuario")

    def __str__(self):
        return f"{self.usuario.username} likes {self.producto.nombre}"

class Sucursal(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="sucursales")
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20, blank=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.empresa.nombre})"

    @property
    def tiene_pedidos(self):
        return self.pedidos.exists()


class Carrito(models.Model):
    cliente = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="carrito")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Carrito de {self.cliente.username}"

    @property
    def total(self):
        total = Decimal("0")
        for item in self.items.select_related("producto", "producto__empresa"):
            total += item.producto.precio_venta * item.cantidad
        return total


class CarritoItem(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="carrito_items")
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("carrito", "producto")

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"


class Pedido(models.Model):
    PENDIENTE = "PENDIENTE"
    PROCESADO = "PROCESADO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"
    ESTADO_CHOICES = (
        (PENDIENTE, "Pendiente"),
        (PROCESADO, "Procesado"),
        (ENTREGADO, "Entregado"),
        (CANCELADO, "Cancelado"),
    )

    EFECTIVO = "EFECTIVO"
    TRANSFERENCIA = "TRANSFERENCIA"
    TARJETA = "TARJETA"
    PAGO_MOVIL = "PAGO_MOVIL"
    METODO_PAGO_CHOICES = (
        (EFECTIVO, "Efectivo al entregar"),
        (TRANSFERENCIA, "Transferencia bancaria"),
        (TARJETA, "Tarjeta al entregar"),
        (PAGO_MOVIL, "Pago móvil / Zelle"),
    )

    cliente = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="pedidos")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="pedidos")
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos"
    )
    empleado = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos_procesados",
    )
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    direccion_entrega = models.CharField(max_length=255, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=PENDIENTE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Pedido #{self.pk} de {self.cliente.username} → {self.empresa.nombre} ({self.estado})"

    def transicion_valida(self, nuevo_estado):
        permitidas = {
            self.PENDIENTE: {self.PROCESADO, self.CANCELADO},
            self.PROCESADO: {self.ENTREGADO, self.CANCELADO},
            self.ENTREGADO: set(),
            self.CANCELADO: set(),
        }
        return nuevo_estado in permitidas.get(self.estado, set())


class PedidoItem(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="pedido_items")
    cantidad = models.PositiveIntegerField()
    precio = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} (pedido {self.pedido_id})"


class ChatMensaje(models.Model):
    emisor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="mensajes_enviados")
    receptor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="mensajes_recibidos")
    mensaje = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, null=True, blank=True, related_name="mensajes")

    class Meta:
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.emisor} -> {self.receptor}: {self.mensaje[:40]}"


class Notificacion(models.Model):
    PEDIDO = "PEDIDO"
    TIPO_CHOICES = (
        (PEDIDO, "Pedido"),
    )

    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="notificaciones")
    titulo = models.CharField(max_length=120)
    mensaje = models.TextField(blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=PEDIDO)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, null=True, blank=True, related_name="notificaciones")
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "tipo", "pedido"],
                name="uniq_notificacion_usuario_tipo_pedido",
            )
        ]

    def __str__(self):
        return f"{self.titulo} → {self.usuario.username} ({'leída' if self.leida else 'no leída'})"
