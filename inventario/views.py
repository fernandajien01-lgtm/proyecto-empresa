from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

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
    SucursalForm,
    SugerenciaForm,
)
from .models import (
    Carrito,
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
    Sucursal,
    Sugerencia,
    ensure_default_categorias,
)


class CustomLoginView(auth_views.LoginView):
    def get_success_url(self):
        url = self.get_redirect_url()
        if url:
            return url
        if self.request.user.is_authenticated and self.request.user.role == "EMPRESA":
            return reverse("dashboard")
        return reverse("producto_list")


def distancia_km(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (TypeError, ValueError):
        return None
    radio = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return radio * 2 * asin(sqrt(a))


def get_or_crear_carrito(user):
    carrito, _ = Carrito.objects.get_or_create(cliente=user)
    return carrito


def empresa_usuario(empresa):
    return CustomUser.objects.filter(role="EMPRESA", empresa=empresa).first()


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
    pedidos = Pedido.objects.filter(empresa=empresa)
    pedidos_pendientes = pedidos.filter(estado=Pedido.PENDIENTE).count()
    sucursales = empresa.sucursales.all()
    movimientos_recientes = (
        Movimiento.objects.filter(producto__empresa=empresa)
        .select_related("producto", "usuario")
        .order_by("-fecha_hora")[:5]
    )

    context = {
        "productos": productos,
        "mas_vendidos": mas_vendidos,
        "menos_vendidos": menos_vendidos,
        "total_unidades_vendidas": total_unidades_vendidas,
        "alertas": alertas,
        "pendientes_recientes": pedidos.filter(estado=Pedido.PENDIENTE).select_related("cliente", "sucursal")[:5],
        "solicitudes": solicitudes,
        "total_productos": productos.count(),
        "stock_bajo": alertas.count(),
        "total_pedidos": pedidos.count(),
        "pedidos_pendientes": pedidos_pendientes,
        "sucursales": sucursales,
        "movimientos_recientes": movimientos_recientes,
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
    return render(request, "solicitudes_empresa.html", {"solicitudes": solicitudes})


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
    productos = Producto.objects.filter(empresa=empresa).select_related("categoria", "proveedor", "empresa")
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
    messages.warning(request, "Las categorías ya vienen predefinidas por el sistema.")
    return redirect("dashboard")


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
                        chats_cliente.append({
                            "empleado": emp,
                            "cliente": cli,
                            "fecha": ultimo.fecha,
                            "pedidos": Pedido.objects.filter(
                                cliente=cli, empresa=request.user.empresa
                            ).order_by("-fecha_creacion")[:3],
                        })
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
            producto.empresa = request.user.empresa or request.user.empresa
            producto.save()
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
        producto = get_object_or_404(Producto, pk=pk, empresa=request.user.empresa)

    if request.method == "POST":
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto actualizado correctamente.")
            return redirect("dashboard" if request.user.role == "EMPRESA" else "producto_list")
    else:
        form = ProductoForm(instance=producto)
    return render(request, "producto_form.html", {"form": form, "accion": "Editar", "producto": producto})


@login_required
def producto_eliminar(request, pk):
    if request.user.role != "EMPRESA":
        return redirect("producto_list")
    producto = get_object_or_404(Producto, pk=pk, empresa=request.user.empresa)
    if request.method == "POST":
        producto.delete()
        messages.success(request, "Producto eliminado correctamente.")
        return redirect("dashboard")
    return render(request, "producto_confirm_delete.html", {"producto": producto})


def _pagina_segura(paginator, raw_page):
    try:
        page = int(raw_page or 1)
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1
    if page > paginator.num_pages:
        page = paginator.num_pages or 1
    return page


def _movimiento_crear_context(request, form):
    context = {"form": form}
    if request.user.role == "EMPLEADO":
        movimientos = (
            Movimiento.objects.filter(usuario=request.user, producto__empresa=request.user.empresa)
            .select_related("producto")
            .order_by("-fecha_hora")
        )
        tipo = request.GET.get("tipo", "")
        if tipo in {Movimiento.TIPO_ENTRADA, Movimiento.TIPO_SALIDA}:
            movimientos = movimientos.filter(tipo_movimiento=tipo)
        else:
            tipo = ""
        paginator = Paginator(movimientos, 20)
        context["movimientos"] = paginator.page(_pagina_segura(paginator, request.GET.get("pagina")))
        context["filtro_tipo"] = tipo
        context["total_movimientos"] = paginator.count
    return context


@login_required
def movimiento_crear(request):
    if request.user.role not in {"EMPRESA", "EMPLEADO"}:
        messages.warning(request, "No tienes permisos para registrar movimientos.")
        return redirect("producto_list")
    if request.user.empresa is None:
        messages.warning(request, "Tu cuenta debe estar asociada a una empresa para registrar movimientos.")
        return redirect("producto_list")
    if request.method == "POST":
        form = MovimientoForm(request.POST, user=request.user)
        if form.is_valid():
            movimiento = form.save(commit=False)
            movimiento.usuario = request.user
            producto = movimiento.producto
            if movimiento.tipo_movimiento == Movimiento.TIPO_ENTRADA:
                producto.cantidad_stock += movimiento.cantidad
            else:
                if producto.cantidad_stock < movimiento.cantidad:
                    form.add_error("cantidad", "No hay stock suficiente para esta salida.")
                    return render(request, "movimiento_form.html", _movimiento_crear_context(request, form))
                producto.cantidad_stock -= movimiento.cantidad
            producto.save()
            movimiento.save()
            messages.success(request, "Movimiento de inventario registrado correctamente.")
            if request.user.role == "EMPRESA":
                return redirect("dashboard")
            return redirect("movimiento_crear")
    else:
        form = MovimientoForm(user=request.user)
    return render(request, "movimiento_form.html", _movimiento_crear_context(request, form))


@login_required
def movimientos_list(request):
    if request.user.role != "EMPRESA" or request.user.empresa is None:
        messages.warning(request, "Solo la empresa puede consultar el historial de movimientos.")
        return redirect("dashboard")
    empresa = request.user.empresa
    movimientos = (
        Movimiento.objects.filter(producto__empresa=empresa)
        .select_related("producto", "usuario")
        .order_by("-fecha_hora")
    )
    empleado_id = request.GET.get("empleado", "")
    if empleado_id and empleado_id.isdigit():
        movimientos = movimientos.filter(usuario_id=int(empleado_id))
    else:
        empleado_id = ""
    tipo = request.GET.get("tipo", "")
    if tipo in {Movimiento.TIPO_ENTRADA, Movimiento.TIPO_SALIDA}:
        movimientos = movimientos.filter(tipo_movimiento=tipo)
    else:
        tipo = ""
    entradas = movimientos.filter(tipo_movimiento=Movimiento.TIPO_ENTRADA)
    salidas = movimientos.filter(tipo_movimiento=Movimiento.TIPO_SALIDA)
    resumen = {
        "total": movimientos.count(),
        "entradas": entradas.count(),
        "salidas": salidas.count(),
        "unidades_entrada": entradas.aggregate(total=Sum("cantidad"))["total"] or 0,
        "unidades_salida": salidas.aggregate(total=Sum("cantidad"))["total"] or 0,
    }
    paginator = Paginator(movimientos, 20)
    empleados = CustomUser.objects.filter(role="EMPLEADO", empresa=empresa).order_by("username")
    return render(
        request,
        "movimientos_list.html",
        {
            "movimientos": paginator.page(_pagina_segura(paginator, request.GET.get("pagina"))),
            "empleados": empleados,
            "filtro_empleado": empleado_id,
            "filtro_tipo": tipo,
            "resumen": resumen,
        },
    )


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


def _reseñas_prefetch(user):
    qs = Resena.objects.annotate(
        total_likes=Count("reacciones", filter=Q(reacciones__tipo=ReaccionResena.LIKE)),
        total_dislikes=Count("reacciones", filter=Q(reacciones__tipo=ReaccionResena.DISLIKE)),
    )
    if user.is_authenticated:
        qs = qs.annotate(
            mi_tipo=Subquery(
                ReaccionResena.objects.filter(resena=OuterRef("pk"), usuario=user).values("tipo")[:1]
            )
        )
    return Prefetch("reseñas", queryset=qs.prefetch_related("reacciones"))


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
        productos = Producto.objects.select_related("categoria", "proveedor", "empresa").filter(empresa=request.user.empresa).all().prefetch_related(_reseñas_prefetch(request.user))
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
            "busqueda_empresa": busqueda_empresa,
            "busqueda_categoria": "",
            "busqueda_producto": "",
            "form": ResenaForm(),
            "categorias": Categoria.objects.all(),
        }
        return render(request, "producto_list.html", context)

    if request.user.is_authenticated and request.user.role == "CLIENTE":
        productos = Producto.objects.select_related("categoria", "proveedor", "empresa").all()
        if busqueda_empresa:
            productos = productos.filter(empresa__nombre__icontains=busqueda_empresa)
        if busqueda_categoria:
            productos = productos.filter(categoria__nombre__icontains=busqueda_categoria)
        if busqueda_producto:
            productos = productos.filter(nombre__icontains=busqueda_producto)

        productos = productos.prefetch_related(_reseñas_prefetch(request.user))

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

    productos = Producto.objects.select_related("categoria", "proveedor", "empresa").all()
    if busqueda_empresa:
        productos = productos.filter(empresa__nombre__icontains=busqueda_empresa)
    if busqueda_categoria:
        productos = productos.filter(categoria__nombre__icontains=busqueda_categoria)
    if busqueda_producto:
        productos = productos.filter(nombre__icontains=busqueda_producto)

    productos = productos.prefetch_related(_reseñas_prefetch(request.user))

    context = {
        "productos": productos,
        "form": ResenaForm(),
        "busqueda_empresa": busqueda_empresa,
        "busqueda_categoria": busqueda_categoria,
        "busqueda_producto": busqueda_producto,
        "categorias": Categoria.objects.all(),
    }
    return render(request, "producto_list.html", context)


@login_required
def reaccion_producto(request, producto_id, tipo):
    if tipo not in {ReaccionProducto.LIKE}:
        messages.error(request, "Tipo de reacción inválido.")
        return redirect("producto_list")
    producto = get_object_or_404(Producto, pk=producto_id)
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
    reaccion = ReaccionResena.objects.filter(resena=resena, usuario=request.user).first()
    if reaccion is not None:
        if reaccion.tipo == tipo:
            reaccion.delete()
            messages.info(request, "Reacción retirada.")
        else:
            reaccion.tipo = tipo
            reaccion.save()
            messages.success(request, "Te gusta esta reseña." if tipo == ReaccionResena.LIKE else "Has marcado esta reseña.")
    else:
        ReaccionResena.objects.create(resena=resena, usuario=request.user, tipo=tipo)
        messages.success(request, "Te gusta esta reseña." if tipo == ReaccionResena.LIKE else "Has marcado esta reseña.")
    return redirect("producto_list")


@login_required
def resena_crear(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id)
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
@require_POST
def carrito_agregar(request, pk):
    if request.user.role != "CLIENTE":
        messages.warning(request, "Solo los clientes pueden usar el carrito de compras.")
        return redirect("producto_list")
    producto = get_object_or_404(Producto, pk=pk)
    try:
        cantidad = int(request.POST.get("cantidad", 1))
    except (TypeError, ValueError):
        cantidad = 1
    if cantidad < 1:
        cantidad = 1
    if producto.cantidad_stock <= 0:
        messages.error(request, "Este producto no tiene stock disponible.")
        return redirect("producto_list")
    if cantidad > producto.cantidad_stock:
        messages.error(
            request,
            f"No hay suficiente stock de {producto.nombre} (disponible: {producto.cantidad_stock}).",
        )
        return redirect("producto_list")
    carrito = get_or_crear_carrito(request.user)
    item, created = CarritoItem.objects.get_or_create(carrito=carrito, producto=producto)
    if created:
        item.cantidad = cantidad
    else:
        nueva = item.cantidad + cantidad
        if nueva > producto.cantidad_stock:
            messages.error(
                request,
                f"No hay suficiente stock de {producto.nombre} (disponible: {producto.cantidad_stock}).",
            )
            return redirect("producto_list")
        item.cantidad = nueva
    item.save()
    messages.success(request, f"{producto.nombre} agregado al carrito ({item.cantidad} uds).")
    return redirect("producto_list")


@login_required
def carrito_detalle(request):
    if request.user.role != "CLIENTE":
        messages.warning(request, "Solo los clientes tienen carrito de compras.")
        return redirect("producto_list")
    carrito = get_or_crear_carrito(request.user)
    items = carrito.items.select_related("producto", "producto__empresa", "producto__categoria")
    return render(request, "carrito.html", {"carrito": carrito, "items": items})


@login_required
@require_POST
def carrito_actualizar(request, item_id):
    if request.user.role != "CLIENTE":
        return redirect("producto_list")
    item = get_object_or_404(CarritoItem, pk=item_id, carrito__cliente=request.user)
    try:
        cantidad = int(request.POST.get("cantidad", 0))
    except (TypeError, ValueError):
        cantidad = 0
    if cantidad <= 0:
        item.delete()
        messages.info(request, f"{item.producto.nombre} se eliminó del carrito.")
    elif cantidad > item.producto.cantidad_stock:
        messages.error(
            request,
            f"No hay suficiente stock de {item.producto.nombre} (disponible: {item.producto.cantidad_stock}).",
        )
    else:
        item.cantidad = cantidad
        item.save()
        messages.success(request, "Carrito actualizado.")
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("carrito_detalle")


@login_required
@require_POST
def carrito_quitar(request, item_id):
    if request.user.role != "CLIENTE":
        return redirect("producto_list")
    item = get_object_or_404(CarritoItem, pk=item_id, carrito__cliente=request.user)
    item.delete()
    messages.info(request, f"{item.producto.nombre} se eliminó del carrito.")
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("carrito_detalle")


@login_required
def carrito_checkout(request):
    if request.user.role != "CLIENTE":
        messages.warning(request, "Solo los clientes pueden realizar compras.")
        return redirect("producto_list")
    carrito = get_or_crear_carrito(request.user)
    items = list(carrito.items.select_related("producto", "producto__empresa"))
    if not items:
        messages.info(request, "Tu carrito está vacío.")
        return redirect("carrito_detalle")

    clat = request.POST.get("clat") or request.GET.get("clat") or ""
    clng = request.POST.get("clng") or request.GET.get("clng") or ""

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            por_empresa = {}
            sin_stock = []
            for item in items:
                if item.cantidad > item.producto.cantidad_stock:
                    sin_stock.append(item.producto.nombre)
                por_empresa.setdefault(item.producto.empresa_id, []).append(item)
            if sin_stock:
                messages.error(request, "Sin stock suficiente para: " + ", ".join(sin_stock))
                return redirect("carrito_checkout")
            creados = 0
            for empresa_id, emp_items in por_empresa.items():
                empresa = emp_items[0].producto.empresa
                sucursal = None
                suc_id = request.POST.get(f"sucursal_{empresa_id}")
                if suc_id:
                    sucursal = Sucursal.objects.filter(pk=suc_id, empresa_id=empresa_id).first()
                total = sum(
                    (i.producto.precio_venta * i.cantidad for i in emp_items),
                    Decimal("0"),
                )
                pedido = Pedido.objects.create(
                    cliente=request.user,
                    empresa=empresa,
                    sucursal=sucursal,
                    metodo_pago=form.cleaned_data["metodo_pago"],
                    direccion_entrega=form.cleaned_data["direccion_entrega"],
                    total=total,
                )
                for i in emp_items:
                    PedidoItem.objects.create(
                        pedido=pedido,
                        producto=i.producto,
                        cantidad=i.cantidad,
                        precio=i.producto.precio_venta,
                    )
                _notificar_nuevo_pedido(pedido)
                creados += 1
            carrito.items.all().delete()
            messages.success(
                request,
                f"Pedido{'s' if creados > 1 else ''} enviado correctamente. "
                "La empresa lo revisará y un empleado gestionará la compra.",
            )
            return redirect("mis_pedidos")
        else:
            messages.error(request, "Revisa el método de pago y la dirección de entrega.")
    else:
        form = CheckoutForm()

    grupos = []
    vistos = set()
    for item in items:
        if item.producto.empresa_id in vistos:
            continue
        vistos.add(item.producto.empresa_id)
        empresa = item.producto.empresa
        emp_items = [i for i in items if i.producto.empresa_id == empresa.id]
        sucursales = list(Sucursal.objects.filter(empresa=empresa))
        for sucursal in sucursales:
            dist = None
            if clat and clng and sucursal.latitud is not None and sucursal.longitud is not None:
                dist = distancia_km(clat, clng, sucursal.latitud, sucursal.longitud)
            sucursal.distancia_km = dist
        sucursales.sort(key=lambda s: (s.distancia_km is None, s.distancia_km or 0))
        grupos.append(
            {
                "empresa": empresa,
                "items": emp_items,
                "sucursales": sucursales,
                "total": sum((i.producto.precio_venta * i.cantidad for i in emp_items), Decimal("0")),
            }
        )
    total_general = sum((i.producto.precio_venta * i.cantidad for i in items), Decimal("0"))
    return render(
        request,
        "checkout.html",
        {
            "grupos": grupos,
            "total_general": total_general,
            "form": form,
            "clat": clat,
            "clng": clng,
        },
    )


@login_required
def mis_pedidos(request):
    if request.user.role != "CLIENTE":
        messages.warning(request, "Solo los clientes tienen pedidos.")
        return redirect("producto_list")
    pedidos = (
        Pedido.objects.filter(cliente=request.user)
        .select_related("empresa", "sucursal", "empleado")
        .prefetch_related("items__producto")
    )
    return render(request, "mis_pedidos.html", {"pedidos": pedidos})


def _thread_pedido(pedido, a, b):
    if a is None or b is None:
        return ChatMensaje.objects.none()
    return (
        ChatMensaje.objects.filter(pedido=pedido)
        .filter(Q(emisor=a, receptor=b) | Q(emisor=b, receptor=a))
        .order_by("fecha")
    )


@login_required
def pedido_detalle(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    es_cliente = request.user.role == "CLIENTE" and pedido.cliente == request.user
    es_responsable = (
        request.user.role == "EMPLEADO"
        and request.user.empresa == pedido.empresa
        and pedido.empleado == request.user
    )
    es_empresa = request.user.role == "EMPRESA" and request.user.empresa == pedido.empresa
    if not (es_cliente or es_responsable or es_empresa):
        messages.warning(request, "No tienes acceso a este pedido.")
        if request.user.role == "CLIENTE":
            return redirect("mis_pedidos")
        return redirect("producto_list")

    if request.method == "POST":
        contenido = (request.POST.get("mensaje") or "").strip()
        modo = request.POST.get("modo", "")
        receptor = None
        if contenido and modo in {"empleado", "empresa"}:
            if modo == "empleado":
                if request.user.role == "CLIENTE":
                    receptor = pedido.empleado
                elif es_responsable:
                    receptor = pedido.cliente
            else:
                if request.user.role == "CLIENTE":
                    receptor = empresa_usuario(pedido.empresa)
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
    empresa_user = empresa_usuario(pedido.empresa)
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
            "es_empleado": es_responsable,
            "es_empresa": es_empresa,
            "puede_enviar_empleado": es_cliente or es_responsable,
            "puede_enviar_empresa": es_cliente or es_empresa,
        },
    )


@login_required
def pedidos_empleado(request):
    if request.user.role != "EMPLEADO" or request.user.empresa is None:
        messages.warning(request, "Solo empleados con empresa pueden gestionar pedidos.")
        return redirect("producto_list")
    empresa = request.user.empresa
    request.user.notificaciones.filter(tipo=Notificacion.PEDIDO, leida=False).update(leida=True)
    pendientes = (
        Pedido.objects.filter(empresa=empresa, estado=Pedido.PENDIENTE)
        .select_related("cliente", "sucursal")
        .prefetch_related("items__producto")
    )
    procesados = (
        Pedido.objects.filter(empresa=empresa, estado=Pedido.PROCESADO)
        .select_related("cliente", "sucursal")
        .prefetch_related("items__producto")
    )
    return render(
        request,
        "pedidos_empleado.html",
        {"pendientes": pendientes, "procesados": procesados},
    )


@login_required
@require_POST
def procesar_pedido(request, pk):
    if request.user.role != "EMPLEADO" or request.user.empresa is None:
        messages.warning(request, "Solo empleados con empresa pueden procesar pedidos.")
        return redirect("producto_list")
    pedido = get_object_or_404(Pedido, pk=pk, empresa=request.user.empresa)
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
            producto.save()
            Movimiento.objects.create(
                producto=producto,
                tipo_movimiento=Movimiento.TIPO_SALIDA,
                cantidad=item.cantidad,
                usuario=request.user,
                nota=f"Pedido #{pedido.pk} procesado por {request.user.username}",
            )
        pedido.empleado = request.user
        pedido.estado = Pedido.PROCESADO
        pedido.save()
    messages.success(request, f"Pedido #{pedido.pk} procesado correctamente; el stock fue descontado.")
    return redirect("pedidos_empleado")


@login_required
def pedidos_empresa(request):
    if request.user.role != "EMPRESA" or request.user.empresa is None:
        messages.warning(request, "Solo la empresa puede supervisar pedidos.")
        return redirect("dashboard")
    empresa = request.user.empresa
    pedidos = (
        Pedido.objects.filter(empresa=empresa)
        .select_related("cliente", "sucursal", "empleado")
        .prefetch_related("items__producto")
    )
    return render(request, "pedidos_empresa.html", {"pedidos": pedidos})


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
    pedido.save()
    messages.success(request, f"Pedido #{pedido.pk} marcado como {pedido.get_estado_display()}.")
    destino = "pedidos_empresa" if es_empresa else "pedidos_empleado"
    return redirect(destino)


@login_required
def sucursales_empresa(request):
    if request.user.role != "EMPRESA" or request.user.empresa is None:
        messages.warning(request, "Solo la empresa puede gestionar sucursales.")
        return redirect("dashboard")
    empresa = request.user.empresa
    if request.method == "POST":
        form = SucursalForm(request.POST)
        if form.is_valid():
            sucursal = form.save(commit=False)
            sucursal.empresa = empresa
            sucursal.save()
            messages.success(request, "Sucursal agregada correctamente.")
            return redirect("sucursales_empresa")
        messages.error(request, "Revisa los datos de la sucursal.")
    else:
        form = SucursalForm()
    sucursales = empresa.sucursales.all()
    return render(request, "sucursal_lista.html", {"sucursales": sucursales, "form": form})


@login_required
def sucursal_editar(request, pk):
    if request.user.role != "EMPRESA" or request.user.empresa is None:
        return redirect("dashboard")
    sucursal = get_object_or_404(Sucursal, pk=pk, empresa=request.user.empresa)
    if sucursal.tiene_pedidos:
        messages.error(request, "Esta sucursal tiene pedidos asignados: no se puede editar su ubicación ni dirección.")
        return redirect("sucursales_empresa")
    if request.method == "POST":
        form = SucursalForm(request.POST, instance=sucursal)
        if form.is_valid():
            form.save()
            messages.success(request, "Sucursal actualizada correctamente.")
            return redirect("sucursales_empresa")
        messages.error(request, "Revisa los datos de la sucursal.")
    else:
        form = SucursalForm(instance=sucursal)
    return render(request, "sucursal_form.html", {"form": form, "sucursal": sucursal})


@login_required
@require_POST
def sucursal_eliminar(request, pk):
    if request.user.role != "EMPRESA" or request.user.empresa is None:
        return redirect("dashboard")
    sucursal = get_object_or_404(Sucursal, pk=pk, empresa=request.user.empresa)
    if sucursal.tiene_pedidos:
        messages.error(request, "Esta sucursal tiene pedidos asignados: no se puede eliminar.")
        return redirect("sucursales_empresa")
    sucursal.delete()
    messages.success(request, "Sucursal eliminada correctamente.")
    return redirect("sucursales_empresa")
