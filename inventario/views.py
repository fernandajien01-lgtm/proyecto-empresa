from datetime import timedelta
from decimal import Decimal
from functools import wraps
import json
import secrets

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import transaction
from django.db.models import F, ProtectedError, Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .geo import haversine_km

from .forms import (
    CategoriaForm,
    CheckoutForm,
    EmpresaForm,
    MovimientoForm,
    ProductoForm,
    ProveedorForm,
    RegistroUsuarioForm,
    ResenaForm,
    SolicitudEmpleadoForm,
    SugerenciaForm,
)
from .models import (
    CarritoItem,
    Categoria,
    ChatMensaje,
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
    ensure_default_categorias,
)


@login_required
def dejar_empresa(request):
    if request.user.role != "EMPLEADO":
        messages.warning(request, "Solo los empleados pueden dejar una empresa.")
        return redirect("producto_list")
    if request.method == "POST":
        empleado = request.user
        empresa = empleado.empresa
        # delete movimientos relacionados del empleado con esta empresa
        if empresa is not None:
            Movimiento.objects.filter(usuario=empleado, producto__empresa=empresa).delete()
        empleado.empresa = None
        empleado.save()
        # Remove pending solicitudes if any
        SolicitudEmpleado.objects.filter(empleado=empleado).delete()
        messages.success(request, "Has dejado la empresa correctamente.")
    return redirect("producto_list")


@login_required
def quitar_empleado(request, empleado_id):
    if request.user.role != "EMPRESA":
        return redirect("producto_list")
    empleado = get_object_or_404(CustomUser, pk=empleado_id, empresa=request.user.empresa)
    if request.method == "POST":
        empresa = request.user.empresa
        # delete movimientos relacionados del empleado con esta empresa
        Movimiento.objects.filter(usuario=empleado, producto__empresa=empresa).delete()
        empleado.empresa = None
        empleado.save()
        SolicitudEmpleado.objects.filter(empleado=empleado).delete()
        messages.success(request, f"Se ha removido a {empleado.username} de la empresa.")
    return redirect("dashboard")


@login_required
def editar_perfil(request):
    if request.user.role not in {"CLIENTE", "EMPLEADO", "EMPRESA"}:
        return redirect("producto_list")
    if request.method == "POST":
        from .forms import UserProfileForm
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado correctamente.")
            return redirect("producto_list")
    else:
        from .forms import UserProfileForm
        form = UserProfileForm(instance=request.user)
    return render(request, "profile_form.html", {"form": form})


@login_required
def confirmar_eliminar_cuenta(request):
    # show confirmation and process deletion
    if request.method == "POST":
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "Tu cuenta ha sido eliminada correctamente.")
        return redirect("producto_list")
    return render(request, "confirmar_eliminar_cuenta.html")


def register(request):
    ensure_default_categorias()
    if request.method == "POST":
        form = RegistroUsuarioForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            user.set_password(form.cleaned_data["password1"])
            user.save()
            login(request, user)
            if user.role == "EMPRESA":
                messages.success(request, "Empresa registrada correctamente.")
                return redirect("dashboard")
            messages.success(request, "Cuenta creada exitosamente.")
            return redirect("producto_list")
    else:
        form = RegistroUsuarioForm()
    return render(
        request,
        "register.html",
        {
            "form": form,
            "company_field_names": [
                "nombre_empresa",
                "rif_empresa",
                "descripcion_empresa",
                "telefono_empresa",
                "direccion_empresa",
            ],
            "contact_field_names": ["cedula", "telefono", "fecha_nacimiento"],
            "employee_field_names": ["residencia", "profile_image"],
        },
    )


@login_required
def custom_logout(request):
    logout(request)
    messages.info(request, "Sesión cerrada correctamente.")
    return redirect("login")


@login_required
def dashboard(request):
    if request.user.role != "EMPRESA":
        messages.warning(request, "Solo la empresa puede acceder al dashboard.")
        return redirect("producto_list")

    empresa = request.user.empresa
    productos = Producto.objects.filter(empresa=empresa).select_related("categoria", "proveedor")
    ventas = (
        Movimiento.objects.filter(producto__empresa=empresa, tipo_movimiento=Movimiento.TIPO_SALIDA)
        .values("producto__id", "producto__nombre")
        .annotate(unidades_vendidas=Sum("cantidad"))
        .order_by("-unidades_vendidas")
    )
    mas_vendidos = list(ventas[:5])
    menos_vendidos = list(
        Movimiento.objects.filter(producto__empresa=empresa, tipo_movimiento=Movimiento.TIPO_SALIDA)
        .values("producto__id", "producto__nombre")
        .annotate(unidades_vendidas=Sum("cantidad"))
        .order_by("unidades_vendidas")[:5]
    )
    total_unidades_vendidas = sum(item["unidades_vendidas"] or 0 for item in ventas)
    alertas = productos.filter(cantidad_stock__lte=F("stock_minimo"))
    solicitudes = SolicitudEmpleado.objects.filter(empresa=empresa).select_related("empleado").order_by("-fecha_creacion")
    por_aprobar = productos.filter(estado=Producto.PENDIENTE)
    rechazados = productos.filter(estado=Producto.RECHAZADO)
    request.user.notificaciones.filter(tipo=Notificacion.PRODUCTO, leida=False).update(leida=True)
    aprobados_empleados = productos.filter(estado=Producto.APROBADO, creado_por__isnull=False).select_related(
        "creado_por", "categoria"
    )

    context = {
        "productos": productos,
        "mas_vendidos": mas_vendidos,
        "menos_vendidos": menos_vendidos,
        "total_unidades_vendidas": total_unidades_vendidas,
        "alertas": alertas,
        "solicitudes": solicitudes,
        "por_aprobar": por_aprobar,
        "rechazados": rechazados,
        "aprobados_empleados": aprobados_empleados,
        "total_productos": productos.count(),
        "stock_bajo": alertas.count(),
    }
    return render(request, "dashboard.html", context)


@login_required
def empresa_editar(request):
    if request.user.role != "EMPRESA":
        messages.warning(request, "Solo la empresa puede editar sus datos.")
        return redirect("producto_list")
    if request.user.empresa is None:
        messages.warning(request, "Tu cuenta no está asociada a una empresa.")
        return redirect("dashboard")

    empresa = request.user.empresa
    if request.method == "POST":
        form = EmpresaForm(request.POST, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, "Datos de la empresa actualizados correctamente.")
            return redirect("dashboard")
    else:
        form = EmpresaForm(instance=empresa)

    return render(request, "empresa_form.html", {"form": form, "accion": "Editar"})


@login_required
def solicitudes_empresa(request):
    if request.user.role != "EMPRESA":
        return redirect("producto_list")
    empresa = request.user.empresa
    solicitudes = SolicitudEmpleado.objects.filter(empresa=empresa).select_related("empleado").order_by("-fecha_creacion")
    pendientes = solicitudes.filter(estado="PENDIENTE").count()
    resueltas = solicitudes.filter(estado__in=["ACEPTADA", "RECHAZADA"]).count()
    return render(
        request,
        "solicitudes_empresa.html",
        {"solicitudes": solicitudes, "pendientes": pendientes, "resueltas": resueltas},
    )


@login_required
def confirmar_aceptar_solicitud(request, pk):
    if request.user.role != "EMPRESA":
        return redirect("producto_list")
    solicitud = get_object_or_404(SolicitudEmpleado, pk=pk, empresa=request.user.empresa)

    if request.method == "POST":
        password = request.POST.get("password", "")
        if request.user.check_password(password):
            empleado = solicitud.empleado
            # Prevent assigning an employee who already belongs to another company
            if empleado.empresa is not None and empleado.empresa != solicitud.empresa:
                messages.error(request, f"El empleado {empleado.username} ya pertenece a otra empresa. No se puede aceptar la solicitud.")
                return redirect("solicitudes_empresa")

            solicitud.estado = SolicitudEmpleado.ACEPTADA
            solicitud.save()
            empleado.empresa = solicitud.empresa
            empleado.role = "EMPLEADO"
            empleado.save()
            messages.success(request, f"Solicitud aceptada para {empleado.username}.")
            return redirect("solicitudes_empresa")
        messages.error(request, "Contraseña incorrecta, no se pudo aceptar la solicitud.")

    return render(request, "confirmar_aceptar_solicitud.html", {"solicitud": solicitud})


@login_required
def actualizar_solicitud(request, pk, estado):
    if request.user.role != "EMPRESA":
        return redirect("producto_list")
    solicitud = get_object_or_404(SolicitudEmpleado, pk=pk, empresa=request.user.empresa)

    if estado == SolicitudEmpleado.ACEPTADA:
        return redirect("confirmar_aceptar_solicitud", pk=solicitud.pk)

    if request.method == "POST":
        solicitud.estado = estado
        solicitud.save()
        messages.warning(request, f"Solicitud rechazada para {solicitud.empleado.username}.")
        return redirect("solicitudes_empresa")

    solicitud.estado = estado
    solicitud.save()
    messages.warning(request, f"Solicitud rechazada para {solicitud.empleado.username}.")
    return redirect("solicitudes_empresa")


@login_required
def mis_solicitudes(request):
    solicitudes = SolicitudEmpleado.objects.filter(empleado=request.user).select_related("empresa").order_by("-fecha_creacion")
    return render(request, "mis_solicitudes.html", {"solicitudes": solicitudes})


@login_required
def solicitar_union_empresa(request, empresa_id):
    if request.user.role != "EMPLEADO":
        messages.warning(request, "Solo los empleados pueden enviar solicitud a una empresa.")
        return redirect("producto_list")
    empresa = get_object_or_404(Empresa, pk=empresa_id)

    # Check for recent cancellation cooldown
    reciente = SolicitudEmpleado.objects.filter(empleado=request.user, empresa=empresa, estado=SolicitudEmpleado.CANCELADA).order_by("-fecha_cancelacion").first()
    if reciente and reciente.fecha_cancelacion:
        from django.utils import timezone
        delta = timezone.now() - reciente.fecha_cancelacion
        if delta.total_seconds() < 24 * 3600:
            remaining = 24 * 3600 - int(delta.total_seconds())
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            messages.warning(request, f"No puedes enviar otra solicitud aún. Intenta de nuevo en {hours}h {minutes}m.")
            return redirect("empresa_detalle", empresa_id=empresa.id)

    solicitud, created = SolicitudEmpleado.objects.get_or_create(empleado=request.user, empresa=empresa)

    if created:
        solicitud.estado = SolicitudEmpleado.PENDIENTE
        solicitud.fecha_cancelacion = None
        solicitud.save()
        messages.success(request, f"Solicitud enviada a {empresa.nombre}.")
    elif solicitud.estado == SolicitudEmpleado.PENDIENTE:
        messages.info(request, f"Ya tienes una solicitud pendiente para {empresa.nombre}.")
    else:
        # If previously processed (ACEPTADA/RECHAZADA/CANCELADA older than cooldown), allow re-send by updating
        solicitud.estado = SolicitudEmpleado.PENDIENTE
        solicitud.fecha_cancelacion = None
        solicitud.save()
        messages.success(request, f"Solicitud reenviada a {empresa.nombre}.")

    return redirect("empresa_detalle", empresa_id=empresa.id)


@login_required
def cancelar_solicitud(request, empresa_id):
    if request.user.role != "EMPLEADO":
        messages.warning(request, "Solo los empleados pueden cancelar solicitudes.")
        return redirect("producto_list")

    empresa = get_object_or_404(Empresa, pk=empresa_id)
    solicitud = SolicitudEmpleado.objects.filter(empleado=request.user, empresa=empresa, estado=SolicitudEmpleado.PENDIENTE).first()
    if solicitud:
        if request.method == "POST":
            from django.utils import timezone
            solicitud.estado = SolicitudEmpleado.CANCELADA
            solicitud.fecha_cancelacion = timezone.now()
            solicitud.save()
            messages.success(request, f"Solicitud a {empresa.nombre} cancelada. Podrás reenviar otra solicitud en 24 horas.")
            return redirect("producto_list")
    else:
        messages.info(request, "No tienes una solicitud pendiente para esa empresa.")
    return redirect("empresa_detalle", empresa_id=empresa.id)


@login_required
def empresa_detalle(request, empresa_id):
    if request.user.role == "EMPRESA":
        return redirect("dashboard")

    empresa = get_object_or_404(Empresa, pk=empresa_id)
    productos = Producto.objects.filter(empresa=empresa, estado=Producto.APROBADO).select_related(
        "categoria", "proveedor", "empresa"
    )
    solicitud = SolicitudEmpleado.objects.filter(empleado=request.user, empresa=empresa).first()
    return render(request, "empresa_detalle.html", {"empresa": empresa, "productos": productos, "solicitud": solicitud})


@login_required
def sugerencia_crear(request):
    if request.user.role not in {"EMPLEADO", "EMPRESA"}:
        messages.warning(request, "Solo empleados o empresas pueden enviar sugerencias.")
        return redirect("producto_list")
    if request.user.empresa is None:
        messages.warning(request, "Tu cuenta debe estar asociada a una empresa para enviar sugerencias.")
        return redirect("producto_list")
    if request.method == "POST":
        form = SugerenciaForm(request.POST)
        if form.is_valid():
            sugerencia = form.save(commit=False)
            sugerencia.empleado = request.user
            sugerencia.empresa = request.user.empresa
            sugerencia.save()
            messages.success(request, "Sugerencia enviada correctamente.")
            return redirect("dashboard" if request.user.role == "EMPRESA" else "producto_list")
    else:
        form = SugerenciaForm()
    return render(request, "sugerencia_form.html", {"form": form})


@login_required
def categoria_crear(request):
    if request.user.role not in {"EMPLEADO", "EMPRESA"}:
        messages.warning(request, "Solo empleados o empresas pueden gestionar categorías.")
        return redirect("producto_list")
    if request.method == "POST":
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f"Categoría '{categoria.nombre}' creada correctamente.")
            return redirect("dashboard" if request.user.role == "EMPRESA" else "producto_list")
    else:
        form = CategoriaForm()
    return render(request, "categoria_form.html", {"form": form, "accion": "Crear"})


@login_required
def categoria_editar(request, pk):
    if request.user.role not in {"EMPLEADO", "EMPRESA"}:
        messages.warning(request, "Solo empleados o empresas pueden gestionar categorías.")
        return redirect("producto_list")
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == "POST":
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, f"Categoría '{categoria.nombre}' actualizada correctamente.")
            return redirect("dashboard" if request.user.role == "EMPRESA" else "producto_list")
    else:
        form = CategoriaForm(instance=categoria)
    return render(
        request, "categoria_form.html", {"form": form, "accion": "Editar", "categoria": categoria}
    )


@login_required
def gestionar_categorias(request):
    if request.user.role not in {"EMPLEADO", "EMPRESA"}:
        messages.warning(request, "Solo empleados o empresas pueden gestionar categorías.")
        return redirect("producto_list")
    if request.method == "POST":
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f"Categoría '{categoria.nombre}' creada correctamente.")
            return redirect("gestionar_categorias")
    else:
        form = CategoriaForm()
    categorias = Categoria.objects.order_by("nombre")
    return render(
        request,
        "gestionar_categorias.html",
        {"form": form, "categorias": categorias},
    )


@login_required
def chat_list(request):
    if request.user.role == "EMPRESA":
        if request.user.empresa is None:
            messages.warning(request, "Tu empresa no está asociada todavía.")
            return redirect("dashboard")
        q = request.GET.get("q", "").strip()
        tipo = request.GET.get("tipo", "empresa")
        empleados = CustomUser.objects.filter(role="EMPLEADO", empresa=request.user.empresa)
        if q:
            filtro = Q(cedula__icontains=q)
            partes = [p for p in q.split(" ") if p]
            if len(partes) >= 2:
                filtro |= Q(first_name__icontains=partes[0], last_name__icontains=partes[-1])
            filtro |= Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q)
            empleados = empleados.filter(filtro)

        chats_empresa = []
        chats_cliente = []
        if tipo == "empresa":
            for emp in empleados:
                ultimo = ChatMensaje.objects.filter(
                    Q(emisor=request.user, receptor=emp) | Q(emisor=emp, receptor=request.user)
                ).order_by("-fecha").first()
                if ultimo:
                    chats_empresa.append({"empleado": emp, "fecha": ultimo.fecha})
        else:
            for emp in empleados:
                clientes = CustomUser.objects.filter(role="CLIENTE").filter(
                    Q(mensajes_enviados__receptor=emp) | Q(mensajes_recibidos__emisor=emp)
                ).distinct()
                for cli in clientes:
                    ultimo = ChatMensaje.objects.filter(
                        Q(emisor=emp, receptor=cli) | Q(emisor=cli, receptor=emp)
                    ).order_by("-fecha").first()
                    if ultimo:
                        chats_cliente.append({"empleado": emp, "cliente": cli, "fecha": ultimo.fecha})
        chats_empresa.sort(key=lambda item: item["fecha"], reverse=True)
        chats_cliente.sort(key=lambda item: item["fecha"], reverse=True)
        return render(
            request,
            "chat_list.html",
            {
                "tipo": tipo,
                "q": q,
                "chats_empresa": chats_empresa,
                "chats_cliente": chats_cliente,
            },
        )

    if request.user.role == "EMPLEADO":
        if request.user.empresa is None:
            messages.warning(request, "Aún no tienes una empresa asociada.")
            return redirect("producto_list")
        empresas = CustomUser.objects.filter(role="EMPRESA", empresa=request.user.empresa)
        return render(request, "chat_list.html", {"usuarios": empresas})

    messages.warning(request, "Solo empleados y empresas pueden chatear.")
    return redirect("producto_list")


@login_required
def chat_con_usuario(request, user_id):
    partner = get_object_or_404(CustomUser, pk=user_id)

    if request.user.role == "EMPRESA":
        if partner.role != "EMPLEADO" or partner.empresa != request.user.empresa:
            messages.warning(request, "No puedes chatear con ese usuario.")
            return redirect("chat_list")
    elif request.user.role == "EMPLEADO":
        if request.user.empresa is None or partner.role != "EMPRESA" or partner.empresa != request.user.empresa:
            messages.warning(request, "No puedes chatear con esa empresa.")
            return redirect("chat_list")
    else:
        messages.warning(request, "No tienes acceso a este chat.")
        return redirect("producto_list")

    if request.method == "POST":
        contenido = (request.POST.get("mensaje") or "").strip()
        if contenido:
            ChatMensaje.objects.create(emisor=request.user, receptor=partner, mensaje=contenido)
            return redirect("chat_con_usuario", user_id=partner.pk)

    mensajes = ChatMensaje.objects.filter(
        Q(emisor=request.user, receptor=partner) | Q(emisor=partner, receptor=request.user)
    ).order_by("fecha")
    return render(request, "chat_detail.html", {"partner": partner, "mensajes": mensajes})


@login_required
def chat_empleado_cliente(request, empleado_id, cliente_id):
    empleado = get_object_or_404(CustomUser, pk=empleado_id, role="EMPLEADO")
    cliente = get_object_or_404(CustomUser, pk=cliente_id, role="CLIENTE")

    empresa_ok = (
        request.user.role == "EMPRESA"
        and request.user.empresa is not None
        and empleado.empresa == request.user.empresa
    )
    if not (empresa_ok or request.user == empleado):
        messages.warning(request, "No tienes acceso a este chat.")
        return redirect("chat_list")

    mensajes = ChatMensaje.objects.filter(
        Q(emisor=empleado, receptor=cliente) | Q(emisor=cliente, receptor=empleado)
    ).order_by("fecha")
    titulo = f"Chat: {empleado.first_name} {empleado.last_name} (Empleado) ↔ {cliente.first_name} {cliente.last_name} (Cliente)"
    return render(
        request,
        "chat_detail.html",
        {"partner": cliente, "mensajes": mensajes, "solo_lectura": True, "titulo_chat": titulo},
    )


@login_required
def proveedor_crear(request):
    if request.user.role != "EMPRESA":
        messages.warning(request, "Solo la empresa puede gestionar proveedores.")
        return redirect("producto_list")
    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Proveedor registrado correctamente.")
            return redirect("dashboard")
    else:
        form = ProveedorForm()
    return render(request, "proveedor_form.html", {"form": form, "accion": "Crear"})


@login_required
def producto_crear(request):
    if request.user.role not in {"EMPRESA", "EMPLEADO"}:
        messages.warning(request, "No tienes permisos para registrar productos.")
        return redirect("producto_list")
    if request.user.role == "EMPLEADO" and request.user.empresa is None:
        messages.warning(request, "Debes pertenecer a una empresa para agregar productos.")
        return redirect("producto_list")
    if request.user.role == "EMPLEADO":
        solicitud = SolicitudEmpleado.objects.filter(empleado=request.user, empresa=request.user.empresa, estado=SolicitudEmpleado.ACEPTADA).exists()
        if not solicitud:
            messages.warning(request, "Solo puedes agregar productos si tu solicitud a la empresa fue aceptada.")
            return redirect("producto_list")
    if request.method == "POST":
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            producto = form.save(commit=False)
            producto.empresa = request.user.empresa
            if request.user.role == "EMPLEADO":
                producto.estado = Producto.PENDIENTE
                producto.creado_por = request.user
            else:
                producto.estado = Producto.APROBADO
            producto.save()
            if request.user.role == "EMPLEADO":
                messages.success(
                    request,
                    "Producto enviado correctamente. Quedará visible en el catálogo cuando la empresa lo apruebe.",
                )
                _notificar_producto_para_aprobacion(producto)
            else:
                messages.success(request, "Producto creado correctamente.")
            return redirect("dashboard" if request.user.role == "EMPRESA" else "producto_list")
    else:
        form = ProductoForm()
    return render(request, "producto_form.html", {"form": form, "accion": "Crear"})


@login_required
def producto_editar(request, pk):
    if request.user.role not in {"EMPRESA", "EMPLEADO"}:
        return redirect("producto_list")

    if request.user.role == "EMPRESA":
        producto = get_object_or_404(Producto, pk=pk, empresa=request.user.empresa)
    else:
        if request.user.empresa is None:
            messages.warning(request, "Debes pertenecer a una empresa para editar productos.")
            return redirect("producto_list")
        solicitud = SolicitudEmpleado.objects.filter(
            empleado=request.user,
            empresa=request.user.empresa,
            estado=SolicitudEmpleado.ACEPTADA,
        ).exists()
        if not solicitud:
            messages.warning(request, "Solo puedes editar productos si tu solicitud a la empresa fue aceptada.")
            return redirect("producto_list")
        producto = get_object_or_404(Producto, pk=pk, empresa=request.user.empresa, creado_por=request.user)

    if request.method == "POST":
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            if request.user.role == "EMPLEADO":
                producto.estado = Producto.PENDIENTE
                producto.save(update_fields=["estado"])
                _notificar_producto_para_aprobacion(producto)
                messages.success(
                    request,
                    "Producto actualizado. Se requiere la aprobación de la empresa para publicarse.",
                )
            else:
                producto.estado = Producto.APROBADO
                producto.save(update_fields=["estado"])
                messages.success(request, "Producto actualizado correctamente.")
            return redirect("dashboard" if request.user.role == "EMPRESA" else "producto_list")
    else:
        form = ProductoForm(instance=producto)
    return render(request, "producto_form.html", {"form": form, "accion": "Editar", "producto": producto})


@login_required
def producto_eliminar(request, pk):
    if request.user.role not in {"EMPRESA", "EMPLEADO"}:
        messages.warning(request, "No tienes permisos para eliminar productos.")
        return redirect("producto_list")

    if request.user.role == "EMPRESA":
        producto = get_object_or_404(Producto, pk=pk, empresa=request.user.empresa)
    else:
        if request.user.empresa is None:
            messages.warning(request, "Debes pertenecer a una empresa para eliminar productos.")
            return redirect("producto_list")
        solicitud = SolicitudEmpleado.objects.filter(
            empleado=request.user,
            empresa=request.user.empresa,
            estado=SolicitudEmpleado.ACEPTADA,
        ).exists()
        if not solicitud:
            messages.warning(request, "Solo puedes eliminar tus productos si tu solicitud a la empresa fue aceptada.")
            return redirect("producto_list")
        producto = get_object_or_404(Producto, pk=pk, creado_por=request.user)

    if request.method == "POST":
        try:
            producto.delete()
        except ProtectedError:
            messages.error(
                request,
                f"No se puede eliminar el producto '{producto.nombre}': tiene pedidos asociados.",
            )
            return redirect("dashboard" if request.user.role == "EMPRESA" else "producto_list")
        messages.success(request, "Producto eliminado correctamente.")
        return redirect("dashboard" if request.user.role == "EMPRESA" else "producto_list")
    return render(request, "producto_confirm_delete.html", {"producto": producto})


@login_required
@require_POST
def aprobar_producto(request, pk, accion):
    if request.user.role != "EMPRESA":
        messages.warning(request, "Solo la empresa puede aprobar productos.")
        return redirect("producto_list")
    producto = get_object_or_404(Producto, pk=pk, empresa=request.user.empresa)
    if accion == "aprobar":
        if producto.estado not in {Producto.PENDIENTE, Producto.RECHAZADO}:
            messages.warning(request, "Este producto ya está aprobado.")
        else:
            producto.estado = Producto.APROBADO
            producto.save(update_fields=["estado"])
            _notificar_resultado_producto(producto, aprobado=True)
            messages.success(request, f"Producto '{producto.nombre}' aprobado y publicado.")
    elif accion == "rechazar":
        if producto.estado != Producto.PENDIENTE:
            messages.warning(request, "Solo se pueden rechazar productos pendientes de aprobación.")
        else:
            motivo = request.POST.get("motivo", "").strip()
            producto.estado = Producto.RECHAZADO
            producto.save(update_fields=["estado"])
            _notificar_resultado_producto(producto, aprobado=False, motivo=motivo)
            messages.success(request, f"Producto '{producto.nombre}' rechazado.")
    else:
        messages.warning(request, "Acción inválida.")
    return redirect("dashboard")


@login_required
def movimiento_crear(request):
    if request.user.role not in {"EMPRESA", "EMPLEADO"}:
        messages.warning(request, "No tienes permisos para registrar movimientos.")
        return redirect("producto_list")
    if request.method == "POST":
        form = MovimientoForm(request.POST)
        if form.is_valid():
            movimiento = form.save(commit=False)
            movimiento.usuario = request.user
            producto = movimiento.producto
            if movimiento.tipo_movimiento == Movimiento.TIPO_ENTRADA:
                producto.cantidad_stock += movimiento.cantidad
            else:
                if producto.cantidad_stock < movimiento.cantidad:
                    form.add_error("cantidad", "No hay stock suficiente para esta salida.")
                    return render(request, "movimiento_form.html", {"form": form})
                producto.cantidad_stock -= movimiento.cantidad
            producto.save()
            movimiento.save()
            messages.success(request, "Movimiento de inventario registrado correctamente.")
            return redirect("dashboard" if request.user.role == "EMPRESA" else "producto_list")
    else:
        form = MovimientoForm()
    return render(request, "movimiento_form.html", {"form": form})


def producto_list(request):
    ensure_default_categorias()

    if request.method == "POST" and "contenido" in request.POST and "producto_id" in request.POST:
        if not request.user.is_authenticated:
            messages.warning(request, "Debes registrarte para comentar productos.")
            return redirect("register")
        if request.user.role == "EMPRESA":
            messages.warning(request, "La empresa no puede comentar productos.")
            return redirect("producto_list")
        product_id = request.POST.get("producto_id")
        producto = get_object_or_404(Producto, pk=product_id)
        resena = Resena(producto=producto, autor=request.user)
        form = ResenaForm(request.POST, initial={"autor": request.user}, instance=resena)
        if form.is_valid():
            resena = form.save(commit=False)
            resena.producto = producto
            resena.autor = request.user
            resena.nombre_anonimo = form.cleaned_data.get("nombre_anonimo") or ""
            resena.calificacion = form.cleaned_data.get("calificacion") or 5
            resena.save()
            messages.success(request, "Comentario registrado correctamente.")
            return redirect("producto_list")
        messages.error(request, "No se pudo guardar el comentario.")
        return redirect("producto_list")

    busqueda_empresa = request.GET.get("empresa", "").strip()
    busqueda_categoria = request.GET.get("categoria", "").strip()
    busqueda_producto = request.GET.get("producto", "").strip()

    if request.user.is_authenticated and request.user.role == "EMPRESA":
        productos = Producto.objects.select_related("categoria", "proveedor", "empresa").filter(empresa=request.user.empresa).all()
        if busqueda_categoria:
            productos = productos.filter(categoria__nombre__icontains=busqueda_categoria)
        if busqueda_producto:
            productos = productos.filter(nombre__icontains=busqueda_producto)
        context = {
            "productos": productos,
            "form": ResenaForm(),
            "busqueda_empresa": busqueda_empresa,
            "busqueda_categoria": busqueda_categoria,
            "busqueda_producto": busqueda_producto,
            "empresas_data": [],
            "categorias": Categoria.objects.all(),
        }
        return render(request, "producto_list.html", context)

    if request.user.is_authenticated and request.user.role == "EMPLEADO":
        mis_productos = (
            Producto.objects.filter(creado_por=request.user)
            .select_related("categoria", "proveedor", "empresa")
        )
        if busqueda_producto or busqueda_categoria:
            productos = (
                Producto.objects.select_related("categoria", "proveedor", "empresa")
                .filter(estado=Producto.APROBADO)
            )
            if busqueda_categoria:
                productos = productos.filter(categoria__nombre__icontains=busqueda_categoria)
            if busqueda_producto:
                productos = productos.filter(nombre__icontains=busqueda_producto)
            context = {
                "productos": productos,
                "mis_productos": mis_productos,
                "form": ResenaForm(),
                "busqueda_empresa": "",
                "busqueda_categoria": busqueda_categoria,
                "busqueda_producto": busqueda_producto,
                "empresas_data": [],
                "categorias": Categoria.objects.all(),
            }
            return render(request, "producto_list.html", context)

        empresas = Empresa.objects.all()
        if busqueda_empresa:
            empresas = empresas.filter(nombre__icontains=busqueda_empresa)

        # Map empresa id to SolicitudEmpleado instance (if any)
        solicitudes = {s.empresa_id: s for s in SolicitudEmpleado.objects.filter(empleado=request.user)}
        empresas_data = []
        from django.utils import timezone
        for empresa in empresas:
            sol = solicitudes.get(empresa.id)
            cooldown_text = None
            if sol and sol.estado == SolicitudEmpleado.CANCELADA and sol.fecha_cancelacion:
                delta = timezone.now() - sol.fecha_cancelacion
                remaining = max(0, 24 * 3600 - int(delta.total_seconds()))
                if remaining > 0:
                    hours = remaining // 3600
                    minutes = (remaining % 3600) // 60
                    seconds = remaining % 60
                    cooldown_text = f"{hours}h {minutes}m {seconds}s"
            empresas_data.append({
                "empresa": empresa,
                "solicitud": sol,
                "cooldown_text": cooldown_text,
            })

        context = {
            "empresas_data": empresas_data,
            "mis_productos": mis_productos,
            "busqueda_empresa": busqueda_empresa,
            "busqueda_categoria": "",
            "busqueda_producto": "",
            "form": ResenaForm(),
            "categorias": Categoria.objects.all(),
        }
        return render(request, "producto_list.html", context)

    if request.user.is_authenticated and request.user.role == "CLIENTE":
        productos = (
            Producto.objects.select_related("categoria", "proveedor", "empresa")
            .filter(estado=Producto.APROBADO)
        )
        if busqueda_empresa:
            productos = productos.filter(empresa__nombre__icontains=busqueda_empresa)
        if busqueda_categoria:
            productos = productos.filter(categoria__nombre__icontains=busqueda_categoria)
        if busqueda_producto:
            productos = productos.filter(nombre__icontains=busqueda_producto)

        context = {
            "productos": productos,
            "form": ResenaForm(),
            "busqueda_empresa": busqueda_empresa,
            "busqueda_categoria": busqueda_categoria,
            "busqueda_producto": busqueda_producto,
            "empresas_data": [],
            "categorias": Categoria.objects.all(),
        }
        return render(request, "producto_list.html", context)

    productos = (
        Producto.objects.select_related("categoria", "proveedor", "empresa")
        .filter(estado=Producto.APROBADO)
    )
    if busqueda_empresa:
        productos = productos.filter(empresa__nombre__icontains=busqueda_empresa)
    if busqueda_categoria:
        productos = productos.filter(categoria__nombre__icontains=busqueda_categoria)
    if busqueda_producto:
        productos = productos.filter(nombre__icontains=busqueda_producto)

    context = {
        "productos": productos,
        "form": ResenaForm(),
        "busqueda_empresa": busqueda_empresa,
        "busqueda_categoria": busqueda_categoria,
        "busqueda_producto": busqueda_producto,
        "empresas_data": [],
        "categorias": Categoria.objects.all(),
    }
    return render(request, "producto_list.html", context)


@login_required
def reaccion_producto(request, producto_id, tipo):
    if tipo not in {ReaccionProducto.LIKE}:
        messages.error(request, "Tipo de reacción inválido.")
        return redirect("producto_list")
    producto = get_object_or_404(Producto, pk=producto_id, estado=Producto.APROBADO)
    reaccion, created = ReaccionProducto.objects.get_or_create(producto=producto, usuario=request.user)
    reaccion.tipo = tipo
    reaccion.save()
    messages.success(request, "Tu reacción a este producto fue registrada.")
    return redirect("producto_list")


@login_required
def reaccion_resena(request, resena_id, tipo):
    if tipo not in {"LIKE", "DISLIKE"}:
        messages.error(request, "Tipo de reacción inválido.")
        return redirect("producto_list")
    resena = get_object_or_404(Resena, pk=resena_id)
    reaccion, created = ReaccionResena.objects.get_or_create(resena=resena, usuario=request.user)
    reaccion.tipo = tipo
    reaccion.save()
    messages.success(request, "Tu reacción a la reseña fue registrada.")
    return redirect("producto_list")


@login_required
def resena_crear(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id, estado=Producto.APROBADO)
    if request.method == "POST":
        form = ResenaForm(request.POST, initial={"autor": request.user if request.user.is_authenticated else None})
        if form.is_valid():
            resena = form.save(commit=False)
            resena.producto = producto
            resena.autor = request.user if request.user.is_authenticated else None
            resena.save()
            messages.success(request, "Comentario agregado correctamente.")
            return redirect("producto_list")
    else:
        form = ResenaForm(initial={"autor": request.user if request.user.is_authenticated else None})
    return render(request, "resena_form.html", {"form": form, "producto": producto})


@login_required
def resena_editar(request, pk):
    resena = get_object_or_404(Resena, pk=pk)
    if resena.autor and resena.autor != request.user:
        messages.error(request, "No puedes editar esta reseña.")
        return redirect("producto_list")
    if not resena.puede_editar():
        messages.error(request, "Las reseñas solo pueden editarse durante las primeras 24 horas.")
        return redirect("producto_list")
    if request.method == "POST":
        form = ResenaForm(request.POST, instance=resena, initial={"autor": resena.autor})
        if form.is_valid():
            form.save()
            messages.success(request, "Reseña actualizada correctamente.")
            return redirect("producto_list")
    else:
        form = ResenaForm(instance=resena, initial={"autor": resena.autor})
    return render(request, "resena_form.html", {"form": form, "producto": resena.producto, "editing": True})


@login_required
def realizar_pedido(request, pk):
    if request.user.role == "EMPLEADO":
        messages.warning(request, "Los empleados no pueden comprar productos.")
        return redirect("producto_list")
    producto = get_object_or_404(Producto, pk=pk, estado=Producto.APROBADO)
    if request.user.role != "CLIENTE":
        messages.warning(request, "Solo los clientes pueden comprar productos.")
        return redirect("producto_list")
    if producto.cantidad_stock <= 0:
        messages.error(request, "Este producto no tiene stock disponible.")
        return redirect("producto_list")

    pedido = Pedido.objects.create(
        cliente=request.user,
        empresa=producto.empresa,
        metodo_pago=Pedido.EFECTIVO,
        direccion_entrega="",
        total=producto.precio_venta,
    )
    PedidoItem.objects.create(pedido=pedido, producto=producto, cantidad=1, precio=producto.precio_venta)
    _notificar_nuevo_pedido(pedido)
    messages.success(request, f"Pedido realizado para {producto.nombre}. Un empleado lo procesará pronto.")
    return redirect("mis_pedidos")


@login_required
def carrito_detalle(request):
    if request.user.role != "CLIENTE":
        messages.warning(request, "Solo los clientes tienen carrito de compras.")
        return redirect("producto_list")
    items = list(
        CarritoItem.objects.filter(usuario=request.user).select_related(
            "producto__empresa", "producto__categoria"
        )
    )
    total = 0
    for item in items:
        item.subtotal = item.producto.precio_venta * item.cantidad
        total += item.subtotal
    return render(request, "carrito.html", {"items": items, "total": total})


@login_required
@require_POST
def carrito_agregar(request, pk):
    if request.user.role != "CLIENTE":
        messages.warning(request, "Solo los clientes pueden usar el carrito de compras.")
        return redirect("producto_list")
    producto = get_object_or_404(Producto, pk=pk, estado=Producto.APROBADO)
    try:
        cantidad = int(request.POST.get("cantidad", "1"))
    except (TypeError, ValueError):
        cantidad = 1
    cantidad = max(1, cantidad)
    item, created = CarritoItem.objects.get_or_create(
        usuario=request.user, producto=producto, defaults={"cantidad": cantidad}
    )
    if not created:
        item.cantidad += cantidad
        item.save()
    messages.success(request, f"{producto.nombre} agregado al carrito ({item.cantidad} uds).")
    return redirect("carrito_detalle")


@login_required
@require_POST
def carrito_actualizar(request, item_id):
    item = get_object_or_404(CarritoItem, pk=item_id, usuario=request.user)
    try:
        cantidad = int(request.POST.get("cantidad", "1"))
    except (TypeError, ValueError):
        cantidad = 1
    if cantidad < 1:
        item.delete()
        messages.info(request, f"{item.producto.nombre} eliminado del carrito.")
    else:
        item.cantidad = cantidad
        item.save()
        messages.info(request, f"Cantidad actualizada de {item.producto.nombre}.")
    return redirect("carrito_detalle")


@login_required
@require_POST
def carrito_quitar(request, item_id):
    item = get_object_or_404(CarritoItem, pk=item_id, usuario=request.user)
    item.delete()
    messages.info(request, f"{item.producto.nombre} eliminado del carrito.")
    return redirect("carrito_detalle")


def _notificar_nuevo_pedido(pedido):
    empleados = CustomUser.objects.filter(role="EMPLEADO", empresa=pedido.empresa)
    for empleado in empleados:
        Notificacion.objects.get_or_create(
            usuario=empleado,
            tipo=Notificacion.PEDIDO,
            pedido=pedido,
            defaults={
                "titulo": f"Nuevo pedido #{pedido.pk}",
                "mensaje": (
                    f"El cliente {pedido.cliente.username} realizó un pedido por "
                    f"${pedido.total}. Revisa para confirmar la compra."
                ),
            },
        )


def _empresa_usuario(empresa):
    return CustomUser.objects.filter(role="EMPRESA", empresa=empresa).first()


def _notificar_producto_para_aprobacion(producto):
    empresa_user = _empresa_usuario(producto.empresa)
    if empresa_user is None:
        return
    autor = producto.creado_por.username if producto.creado_por else "Un empleado"
    Notificacion.objects.update_or_create(
        usuario=empresa_user,
        tipo=Notificacion.PRODUCTO,
        titulo=f"Producto por aprobar: {producto.nombre}",
        defaults={
            "mensaje": f"{autor} solicitó aprobar el producto '{producto.nombre}'. Revisa el dashboard.",
            "leida": False,
        },
    )


def _notificar_resultado_producto(producto, aprobado, motivo=""):
    creador = producto.creado_por
    if creador is None:
        return
    estado = "aprobado" if aprobado else "rechazado"
    verbo = "aprobó" if aprobado else "rechazó"
    mensaje = f"La empresa {verbo} el producto '{producto.nombre}'."
    if not aprobado and motivo:
        mensaje += f" Motivo: {motivo}"
    Notificacion.objects.create(
        usuario=creador,
        tipo=Notificacion.PRODUCTO,
        titulo=f"Producto {estado}: {producto.nombre}",
        mensaje=mensaje,
    )


def _thread_pedido(pedido, a, b):
    if a is None or b is None or a == b:
        return ChatMensaje.objects.none()
    return (
        ChatMensaje.objects.filter(pedido=pedido)
        .filter(Q(emisor=a, receptor=b) | Q(emisor=b, receptor=a))
        .order_by("fecha")
    )


METODOS_PAGO_INFO = {
    "EFECTIVO": "Pagarás en efectivo al empleado en el momento de la entrega.",
    "TRANSFERENCIA": "Realiza una transferencia o depósito a la cuenta de la empresa y confírmalo por el chat del pedido.",
    "TARJETA": "Paga con tarjeta de débito o crédito cuando recibas el pedido.",
    "PAGO_MOVIL": "Usa pago móvil o Zelle; el empleado te indicará el titular al confirmar el pedido.",
}


@login_required
def carrito_checkout(request):
    if request.user.role != "CLIENTE":
        messages.warning(request, "Solo los clientes pueden realizar compras.")
        return redirect("producto_list")
    items = list(CarritoItem.objects.filter(usuario=request.user).select_related("producto", "producto__empresa"))
    if not items:
        messages.info(request, "Tu carrito está vacío.")
        return redirect("carrito_detalle")

    por_empresa = {}
    for item in items:
        por_empresa.setdefault(item.producto.empresa_id, []).append(item)

    grupos = []
    total = Decimal("0")
    for empresa_id, emp_items in por_empresa.items():
        subtotal = sum((i.producto.precio_venta * i.cantidad for i in emp_items), Decimal("0"))
        total += subtotal
        grupos.append({"empresa": emp_items[0].producto.empresa, "items": emp_items, "subtotal": subtotal})

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            sin_stock = [
                i.producto.nombre for i in items if i.cantidad > i.producto.cantidad_stock
            ]
            if sin_stock:
                messages.error(request, "Sin stock suficiente para: " + ", ".join(sin_stock))
                return redirect("carrito_checkout")
            creados = 0
            for empresa_id, emp_items in por_empresa.items():
                empresa = emp_items[0].producto.empresa
                subtotal = sum((i.producto.precio_venta * i.cantidad for i in emp_items), Decimal("0"))
                pedido = Pedido.objects.create(
                    cliente=request.user,
                    empresa=empresa,
                    metodo_pago=form.cleaned_data["metodo_pago"],
                    direccion_entrega=form.cleaned_data["direccion_entrega"],
                    latitud=form.cleaned_data.get("latitud"),
                    longitud=form.cleaned_data.get("longitud"),
                    total=subtotal,
                )
                PedidoItem.objects.bulk_create(
                    [
                        PedidoItem(pedido=pedido, producto=i.producto, cantidad=i.cantidad, precio=i.producto.precio_venta)
                        for i in emp_items
                    ]
                )
                _notificar_nuevo_pedido(pedido)
                creados += 1
            CarritoItem.objects.filter(usuario=request.user).delete()
            messages.success(
                request,
                f"Pedido{'s' if creados > 1 else ''} realizado correctamente. Un empleado lo procesará pronto.",
            )
            return redirect("mis_pedidos")
    else:
        form = CheckoutForm(initial={"metodo_pago": Pedido.EFECTIVO})
    metodos_pago = [
        {
            "value": value,
            "label": label,
            "detalle": METODOS_PAGO_INFO.get(value, ""),
        }
        for value, label in Pedido.METODO_PAGO_CHOICES
    ]
    return render(
        request,
        "checkout.html",
        {"items": items, "grupos": grupos, "total": total, "form": form, "metodos_pago": metodos_pago},
    )


@login_required
def mis_pedidos(request):
    if request.user.role != "CLIENTE":
        messages.warning(request, "Solo los clientes tienen pedidos.")
        return redirect("producto_list")
    pedidos = (
        Pedido.objects.filter(cliente=request.user)
        .select_related("empresa", "empleado")
        .prefetch_related("items__producto")
    )
    return render(request, "mis_pedidos.html", {"pedidos": pedidos})


def _pedido_visible_para(usuario, pedido):
    """¿Puede usuario ver el pedido? Cliente dueño, la empresa o cualquier empleado de ella."""
    if usuario.role == "CLIENTE":
        return pedido.cliente_id == usuario.id
    if usuario.role == "EMPRESA":
        return usuario.empresa_id is not None and usuario.empresa_id == pedido.empresa_id
    if usuario.role == "EMPLEADO":
        return usuario.empresa_id is not None and usuario.empresa_id == pedido.empresa_id
    return False


def _pedidos_activos_empleado(empleado):
    """Pedidos a cargo del empleado que aún no se han entregado (pendientes + procesados)."""
    return Pedido.objects.filter(
        empleado=empleado, estado__in=[Pedido.PENDIENTE, Pedido.PROCESADO]
    ).count()


def _coordenadas_validas(lat, lon):
    if lat is None or lon is None:
        return False
    lat_f = float(lat)
    lon_f = float(lon)
    return -90 <= lat_f <= 90 and -180 <= lon_f <= 180


def _clasificar_disponibles(pedidos, lat, lon, radio_km):
    """Separa pedidos disponibles en (cerca, otros) por distancia desde (lat, lon).

    Los pedidos sin coordenadas se incluyen en 'otros' para que ninguno se pierda.
    Los pedidos con coordenadas se anotan con el atributo _distancia_km.
    """
    cerca = []
    otros = []
    for p in pedidos:
        if (
            _coordenadas_validas(lat, lon)
            and _coordenadas_validas(p.latitud, p.longitud)
        ):
            distancia = haversine_km(float(lat), float(lon), float(p.latitud), float(p.longitud))
            p.distancia_km = round(distancia, 1)
            if distancia <= radio_km:
                cerca.append(p)
            else:
                otros.append(p)
        else:
            otros.append(p)
    cerca.sort(key=lambda p: p.distancia_km)
    return cerca, otros


@login_required
def pedido_detalle(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    es_cliente = request.user.role == "CLIENTE" and pedido.cliente == request.user
    es_empleado = request.user.role == "EMPLEADO" and request.user.empresa_id == pedido.empresa_id
    es_responsable = es_empleado and pedido.empleado == request.user
    es_empresa = request.user.role == "EMPRESA" and request.user.empresa_id == pedido.empresa_id
    if not _pedido_visible_para(request.user, pedido):
        messages.warning(request, "No tienes acceso a este pedido.")
        if request.user.role == "CLIENTE":
            return redirect("mis_pedidos")
        if request.user.role == "EMPLEADO":
            return redirect("pedidos_empleado")
        return redirect("producto_list")

    if request.method == "POST":
        contenido = (request.POST.get("mensaje") or "").strip()
        modo = request.POST.get("modo", "")
        receptor = None
        if contenido and modo in {"empleado", "empresa"}:
            if modo == "empleado":
                if es_cliente:
                    receptor = pedido.empleado
                elif es_responsable:
                    receptor = pedido.cliente
            else:
                if es_cliente:
                    receptor = _empresa_usuario(pedido.empresa)
                elif es_empresa:
                    receptor = pedido.cliente
            if receptor is not None:
                ChatMensaje.objects.create(
                    emisor=request.user,
                    receptor=receptor,
                    mensaje=contenido,
                    pedido=pedido,
                )
            else:
                messages.warning(request, "El contacto indicado no está disponible aún.")
        return redirect("pedido_detalle", pk=pedido.pk)

    empleado = pedido.empleado
    empresa_user = _empresa_usuario(pedido.empresa)
    items = pedido.items.select_related("producto")
    return render(
        request,
        "pedido_detalle.html",
        {
            "pedido": pedido,
            "items": items,
            "empleado": empleado,
            "empresa_user": empresa_user,
            "mensajes_empleado": _thread_pedido(pedido, pedido.cliente, empleado),
            "mensajes_empresa": _thread_pedido(pedido, pedido.cliente, empresa_user),
            "es_cliente": es_cliente,
            "es_empleado": es_empleado,
            "es_responsable": es_responsable,
            "es_empresa": es_empresa,
            "puede_enviar_empleado": (es_cliente and empleado is not None) or es_responsable,
            "puede_enviar_empresa": (es_cliente and empresa_user is not None) or es_empresa,
        },
    )


@login_required
def pedidos_empleado(request):
    if request.user.role != "EMPLEADO" or request.user.empresa is None:
        messages.warning(request, "Solo empleados con empresa pueden gestionar pedidos.")
        return redirect("producto_list")
    empresa = request.user.empresa
    request.user.notificaciones.filter(tipo=Notificacion.PEDIDO, leida=False).update(leida=True)
    pool = (
        Pedido.objects.filter(empresa=empresa, estado=Pedido.PENDIENTE, empleado__isnull=True)
        .select_related("cliente")
        .prefetch_related("items__producto")
    )
    cerca, otros = _clasificar_disponibles(
        pool, request.user.latitud, request.user.longitud, settings.RADIO_KM
    )
    mis_pedidos = (
        Pedido.objects.filter(
            empresa=empresa,
            empleado=request.user,
            estado__in=[Pedido.PENDIENTE, Pedido.PROCESADO],
        )
        .select_related("cliente")
        .prefetch_related("items__producto")
    )
    activos = _pedidos_activos_empleado(request.user)
    return render(
        request,
        "pedidos_empleado.html",
        {
            "cerca": cerca,
            "otros": otros,
            "mis_pedidos": mis_pedidos,
            "activos": activos,
            "al_limite": activos >= settings.LIMITE_PEDIDOS_EMPLEADO,
            "limite": settings.LIMITE_PEDIDOS_EMPLEADO,
            "radio_km": settings.RADIO_KM,
            "tiene_ubicacion": _coordenadas_validas(request.user.latitud, request.user.longitud),
        },
    )


@login_required
@require_POST
def tomar_pedido(request, pk):
    if request.user.role != "EMPLEADO" or request.user.empresa is None:
        messages.warning(request, "Solo empleados con empresa pueden tomar pedidos.")
        return redirect("producto_list")
    pedido = get_object_or_404(
        Pedido, pk=pk, empresa=request.user.empresa, estado=Pedido.PENDIENTE, empleado__isnull=True
    )
    if _pedidos_activos_empleado(request.user) >= settings.LIMITE_PEDIDOS_EMPLEADO:
        messages.error(
            request,
            "Ya tienes el máximo de pedidos a cargo ({lim}). "
            "Termina o libera uno antes de tomar otro.".format(lim=settings.LIMITE_PEDIDOS_EMPLEADO),
        )
        return redirect("pedidos_empleado")
    pedido.empleado = request.user
    pedido.save(update_fields=["empleado", "fecha_actualizacion"])
    messages.success(request, f"Has tomado el pedido #{pedido.pk}. Ahora está a tu cargo.")
    return redirect("pedidos_empleado")


@login_required
@require_POST
def liberar_pedido(request, pk):
    if request.user.role != "EMPLEADO" or request.user.empresa is None:
        messages.warning(request, "Solo empleados con empresa pueden liberar pedidos.")
        return redirect("producto_list")
    pedido = get_object_or_404(Pedido, pk=pk, empresa=request.user.empresa, empleado=request.user)
    if pedido.estado not in {Pedido.PENDIENTE, Pedido.PROCESADO}:
        messages.warning(request, "Este pedido ya está entregado o cancelado; no se puede liberar.")
        return redirect("pedidos_empleado")
    motivo = (request.POST.get("motivo") or "").strip()
    if not motivo:
        messages.error(request, "Indica el motivo para liberar el pedido.")
        return redirect("pedido_detalle", pk=pedido.pk)
    titulo = f"Pedido #{pedido.pk} liberado"
    texto = (
        f"{request.user.get_full_name() or request.user.username} "
        f"no puede realizar tu pedido #{pedido.pk}. Motivo: {motivo}"
    )
    empresa_user = _empresa_usuario(pedido.empresa)
    for destinatario in (pedido.cliente, empresa_user):
        if destinatario is None:
            continue
        notif, _ = Notificacion.objects.get_or_create(
            usuario=destinatario,
            tipo=Notificacion.PEDIDO,
            pedido=pedido,
            defaults={"titulo": titulo, "mensaje": texto},
        )
        if not notif.leida:
            notif.titulo = titulo
            notif.mensaje = texto
            notif.save(update_fields=["titulo", "mensaje"])
    pedido.empleado = None
    pedido.estado = Pedido.PENDIENTE
    pedido.save(update_fields=["empleado", "estado", "fecha_actualizacion"])
    messages.success(
        request,
        f"Pedido #{pedido.pk} liberado. Se notificó a la empresa y al cliente del cambio.",
    )
    return redirect("pedidos_empleado")


@login_required
@require_POST
def guardar_ubicacion(request):
    if request.user.role != "EMPLEADO" or request.user.empresa is None:
        messages.warning(request, "Solo empleados pueden guardar su ubicación.")
        return redirect("producto_list")
    lat = (request.POST.get("latitud") or "").strip()
    lon = (request.POST.get("longitud") or "").strip()
    if not _coordenadas_validas(lat, lon):
        messages.error(request, "Coordenadas no válidas. Indica latitud (-90 a 90) y longitud (-180 a 180).")
        return redirect("pedidos_empleado")
    request.user.latitud = lat
    request.user.longitud = lon
    request.user.save(update_fields=["latitud", "longitud"])
    messages.success(request, "Ubicación guardada. Ahora podrás ver los pedidos cerca de ti.")
    return redirect("pedidos_empleado")


@login_required
@require_POST
def procesar_pedido(request, pk):
    if request.user.role != "EMPLEADO" or request.user.empresa is None:
        messages.warning(request, "Solo empleados con empresa pueden procesar pedidos.")
        return redirect("producto_list")
    pedido = get_object_or_404(Pedido, pk=pk, empresa=request.user.empresa)
    if pedido.empleado != request.user:
        messages.warning(
            request,
            "Solo el empleado que tomó este pedido puede procesarlo.",
        )
        return redirect("pedidos_empleado")
    if pedido.estado != Pedido.PENDIENTE:
        messages.warning(request, "Este pedido ya no está pendiente de procesar.")
        return redirect("pedidos_empleado")
    sin_stock = [item for item in pedido.items.all() if item.cantidad > item.producto.cantidad_stock]
    if sin_stock:
        nombres = ", ".join(i.producto.nombre for i in sin_stock)
        messages.error(request, f"No hay suficiente stock para: {nombres}. Repón el inventario antes de procesar.")
        return redirect("pedido_detalle", pk=pedido.pk)
    with transaction.atomic():
        for item in pedido.items.select_related("producto"):
            producto = item.producto
            producto.cantidad_stock -= item.cantidad
            producto.save(update_fields=["cantidad_stock"])
            Movimiento.objects.create(
                producto=producto,
                tipo_movimiento=Movimiento.TIPO_SALIDA,
                cantidad=item.cantidad,
                usuario=request.user,
                nota=f"Pedido #{pedido.pk} procesado por {request.user.username}",
            )
        pedido.empleado = request.user
        pedido.estado = Pedido.PROCESADO
        pedido.save(update_fields=["empleado", "estado", "fecha_actualizacion"])
    pedido.notificaciones.filter(tipo=Notificacion.PEDIDO, leida=False).update(leida=True)
    messages.success(request, f"Pedido #{pedido.pk} procesado correctamente; el stock fue descontado.")
    return redirect("pedidos_empleado")


@login_required
def pedidos_empresa(request):
    if request.user.role != "EMPRESA" or request.user.empresa is None:
        messages.warning(request, "Solo la empresa puede supervisar pedidos.")
        return redirect("dashboard")
    request.user.notificaciones.filter(tipo=Notificacion.PEDIDO, leida=False).update(leida=True)
    empresa = request.user.empresa
    pedidos = (
        Pedido.objects.filter(empresa=empresa)
        .select_related("cliente", "empleado")
        .prefetch_related("items__producto")
    )
    total = pedidos.count()
    pendientes = pedidos.filter(estado="PENDIENTE").count()
    en_proceso = pedidos.filter(estado__in=["PROCESADO", "ENTREGADO"]).count()
    cancelados = pedidos.filter(estado="CANCELADO").count()
    return render(
        request,
        "pedidos_empresa.html",
        {
            "pedidos": pedidos,
            "total_pedidos": total,
            "pendientes": pendientes,
            "en_proceso": en_proceso,
            "cancelados": cancelados,
        },
    )


@login_required
@require_POST
def cambiar_estado_pedido(request, pk, estado):
    es_empresa = request.user.role == "EMPRESA" and request.user.empresa is not None
    es_empleado = request.user.role == "EMPLEADO" and request.user.empresa is not None
    if not (es_empresa or es_empleado):
        messages.warning(request, "No tienes permisos para cambiar el estado del pedido.")
        return redirect("producto_list")
    if estado not in {Pedido.ENTREGADO, Pedido.CANCELADO}:
        messages.error(request, "Estado no permitido.")
        return redirect("producto_list")
    pedido = get_object_or_404(Pedido, pk=pk, empresa=request.user.empresa)
    if not pedido.transicion_valida(estado):
        labels = dict(Pedido.ESTADO_CHOICES)
        messages.error(
            request,
            f"No se puede pasar de {pedido.get_estado_display()} a {labels[estado]}.",
        )
        return redirect("pedido_detalle", pk=pedido.pk)
    pedido.estado = estado
    pedido.save(update_fields=["estado", "fecha_actualizacion"])
    pedido.notificaciones.filter(tipo=Notificacion.PEDIDO, leida=False).update(leida=True)
    messages.success(request, f"Pedido #{pedido.pk} marcado como {pedido.get_estado_display()}.")
    destino = "pedidos_empresa" if es_empresa else "pedidos_empleado"
    return redirect(destino)


def _empresa_desde_token(request):
    valor = None
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if auth.lower().startswith("token "):
        valor = auth[6:].strip()
    if not valor:
        valor = request.GET.get("token") or request.headers.get("X-Api-Key")
    if not valor:
        return None
    instancia = TokenEmpresa.objects.select_related("usuario").filter(
        token=valor, usuario__role="EMPRESA", usuario__empresa__isnull=False
    ).first()
    return instancia


def token_empresa_requerido(vista):
    @wraps(vista)
    def _envoltura(request, *args, **kwargs):
        instancia = _empresa_desde_token(request)
        if instancia is None:
            if request.headers.get("accept") == "application/json" or request.path.startswith("/api/"):
                return JsonResponse(
                    {"error": "Token de acceso inválido o no autorizado."},
                    status=401,
                )
            raise Http404
        request.token_empresa = instancia
        request.api_empresa = instancia.usuario.empresa
        return vista(request, *args, **kwargs)

    return _envoltura


@login_required
def token_empresa_gestion(request):
    if request.user.role != "EMPRESA" or not request.user.empresa:
        messages.warning(request, "Solo las empresas pueden gestionar su token de acceso.")
        return redirect("producto_list")

    if request.method == "POST":
        accion = request.POST.get("accion", "regenerar")
        instancia, _ = TokenEmpresa.generar(
            request.user,
            descripcion=request.POST.get("descripcion", "").strip(),
        )
        if accion == "regenerar":
            messages.success(request, "Token regenerado. Guarda la información en un lugar seguro.")
        else:
            messages.success(request, "Token de acceso actualizado.")
        return redirect("token_empresa_gestion")

    instancia = TokenEmpresa.objects.filter(usuario=request.user).first()
    contexto = {
        "token_activo": instancia,
    }
    return render(request, "token_empresa.html", contexto)


@token_empresa_requerido
def api_datos_empresa(request):
    empresa = request.api_empresa
    pedidos = Pedido.objects.filter(empresa=empresa)
    pedidos_activos = pedidos.exclude(estado__in=[Pedido.ENTREGADO, Pedido.CANCELADO]).count()
    datos = {
        "empresa": {
            "id": empresa.pk,
            "nombre": empresa.nombre,
            "descripcion": empresa.descripcion,
            "telefono": empresa.telefono,
            "email": empresa.email,
            "instagram": empresa.instagram,
            "pagina_web": empresa.pagina_web,
        },
        "kpis": {
            "total_pedidos": pedidos.count(),
            "pendientes": pedidos.filter(estado=Pedido.PENDIENTE).count(),
            "procesados": pedidos.filter(estado=Pedido.PROCESADO).count(),
            "entregados": pedidos.filter(estado=Pedido.ENTREGADO).count(),
            "cancelados": pedidos.filter(estado=Pedido.CANCELADO).count(),
            "pedidos_activos": pedidos_activos,
        },
        "empleados": list(
            CustomUser.objects.filter(empresa=empresa, role="EMPLEADO").values_list("username", flat=True)
        ),
    }
    return JsonResponse(datos)


@token_empresa_requerido
def api_pedidos_empresa(request):
    empresa = request.api_empresa
    pedidos = (
        Pedido.objects.filter(empresa=empresa)
        .select_related("cliente", "empleado")
        .order_by("-fecha_creacion")
        [:50]
    )
    datos = [
        {
            "id": p.pk,
            "estado": p.estado,
            "total": str(p.total),
            "cliente": p.cliente.username if p.cliente else None,
            "empleado": p.empleado.username if p.empleado else None,
            "items": [
                {"producto": i.producto.nombre, "cantidad": i.cantidad, "precio": str(i.precio)}
                for i in p.items.all()
            ],
        }
        for p in pedidos
    ]
    return JsonResponse({"pedidos": datos})
