from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Categoria,
    CustomUser,
    Empresa,
    Movimiento,
    Producto,
    Proveedor,
    ReaccionProducto,
    ReaccionResena,
    Resena,
    SolicitudEmpleado,
    Sugerencia,
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "empresa")
    fieldsets = UserAdmin.fieldsets + (
        ("Rol y empresa", {"fields": ("role", "empresa")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Rol y empresa", {"fields": ("role", "empresa")}),
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
