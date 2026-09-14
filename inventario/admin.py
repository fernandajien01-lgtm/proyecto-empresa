from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Carrito,
    CarritoItem,
    Categoria,
    CustomUser,
    Empresa,
    Movimiento,
    Pedido,
    PedidoItem,
    Producto,
    Proveedor,
    ReaccionProducto,
    ReaccionResena,
    Resena,
    SolicitudEmpleado,
    Sucursal,
    Sugerencia,
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "empresa", "cedula", "telefono", "residencia")
    fieldsets = UserAdmin.fieldsets + (
        ("Rol y empresa", {"fields": ("role", "empresa")}),
        ("Datos del empleado", {"fields": ("cedula", "telefono", "residencia", "fecha_nacimiento", "profile_image")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Rol y empresa", {"fields": ("role", "empresa")}),
        ("Datos del empleado", {"fields": ("cedula", "telefono", "residencia", "fecha_nacimiento", "profile_image")}),
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


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "direccion", "telefono")


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "fecha_creacion")


@admin.register(CarritoItem)
class CarritoItemAdmin(admin.ModelAdmin):
    list_display = ("carrito", "producto", "cantidad")


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "empresa", "estado", "metodo_pago", "total", "fecha_creacion")
    list_filter = ("estado", "metodo_pago", "empresa")


@admin.register(PedidoItem)
class PedidoItemAdmin(admin.ModelAdmin):
    list_display = ("pedido", "producto", "cantidad", "precio")
