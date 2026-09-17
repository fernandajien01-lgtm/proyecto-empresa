from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    CarritoItem,
    Categoria,
    CustomUser,
    Empresa,
    Movimiento,
    Notificacion,
    Pedido,
    PedidoItem,
    Producto,
    Proveedor,
    ReaccionProducto,
    ReaccionResena,
    Resena,
    SolicitudEmpleado,
    Sugerencia,
    TokenEmpresa,
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "empresa", "cedula", "telefono", "residencia")
    fieldsets = UserAdmin.fieldsets + (
        ("Rol y empresa", {"fields": ("role", "empresa")}),
        ("Datos del empleado", {"fields": ("cedula", "telefono", "residencia", "fecha_nacimiento", "profile_image", "latitud", "longitud")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Rol y empresa", {"fields": ("role", "empresa")}),
        ("Datos del empleado", {"fields": ("cedula", "telefono", "residencia", "fecha_nacimiento", "profile_image", "latitud", "longitud")}),
    )


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "email")


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre",)


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("nombre_negocio", "telefono", "email")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo_sku", "empresa", "categoria", "cantidad_stock", "precio_venta")
    search_fields = ("nombre", "codigo_sku")


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ("producto", "tipo_movimiento", "cantidad", "fecha_hora", "usuario")


@admin.register(SolicitudEmpleado)
class SolicitudEmpleadoAdmin(admin.ModelAdmin):
    list_display = ("empleado", "empresa", "estado", "fecha_creacion")


@admin.register(Sugerencia)
class SugerenciaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "empleado", "empresa", "fecha")


@admin.register(Resena)
class ResenaAdmin(admin.ModelAdmin):
    list_display = ("producto", "autor", "nombre_anonimo", "fecha_creacion")


@admin.register(ReaccionResena)
class ReaccionResenaAdmin(admin.ModelAdmin):
    list_display = ("resena", "usuario", "tipo")


@admin.register(ReaccionProducto)
class ReaccionProductoAdmin(admin.ModelAdmin):
    list_display = ("producto", "usuario", "tipo")


@admin.register(CarritoItem)
class CarritoItemAdmin(admin.ModelAdmin):
    list_display = ("usuario", "producto", "cantidad")
    search_fields = ("usuario__username", "producto__nombre")


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "empresa", "empleado", "metodo_pago", "total", "estado", "fecha_creacion")
    list_filter = ("estado", "metodo_pago")
    search_fields = ("cliente__username", "empresa__nombre")
    readonly_fields = ("latitud", "longitud")


@admin.register(PedidoItem)
class PedidoItemAdmin(admin.ModelAdmin):
    list_display = ("pedido", "producto", "cantidad", "precio")
    search_fields = ("pedido_id", "producto__nombre")


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo", "titulo", "pedido", "leida", "fecha_creacion")
    list_filter = ("tipo", "leida")


@admin.register(TokenEmpresa)
class TokenEmpresaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "token", "created", "updated")
    list_filter = ("created", "updated")
    search_fields = ("token", "usuario__username", "descripcion")
    readonly_fields = ("token", "created", "updated")
