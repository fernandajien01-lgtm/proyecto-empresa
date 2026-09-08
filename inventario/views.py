from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    CategoriaForm,
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
    Categoria,
    ChatMensaje,
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
    ensure_default_categorias,
)


def register(request):
    ensure_default_categorias()
    if request.method == "POST":
        form = RegistroUsuarioForm(request.POST)
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
    return render(request, "register.html", {"form": form})


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

    context = {
        "productos": productos,
        "mas_vendidos": mas_vendidos,
        "menos_vendidos": menos_vendidos,
        "total_unidades_vendidas": total_unidades_vendidas,
        "alertas": alertas,
        "solicitudes": solicitudes,
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
    return render(request, "solicitudes_empresa.html", {"solicitudes": solicitudes})


@login_required
def confirmar_aceptar_solicitud(request, pk):
    if request.user.role != "EMPRESA":
        return redirect("producto_list")
    solicitud = get_object_or_404(SolicitudEmpleado, pk=pk, empresa=request.user.empresa)

    if request.method == "POST":
        password = request.POST.get("password", "")
        if request.user.check_password(password):
            solicitud.estado = SolicitudEmpleado.ACEPTADA
            solicitud.save()
            empleado = solicitud.empleado
            empleado.empresa = solicitud.empresa
            empleado.role = "EMPLEADO"
            empleado.save()
            messages.success(request, f"Solicitud aceptada para {empleado.username}.")
            return redirect("solicitudes_empresa")
        messages.error(request, "La contraseña no es correcta. No se pudo aceptar la solicitud.")

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
    solicitud, created = SolicitudEmpleado.objects.get_or_create(empleado=request.user, empresa=empresa)

    if created:
        solicitud.estado = SolicitudEmpleado.PENDIENTE
        solicitud.save()
        messages.success(request, f"Solicitud enviada a {empresa.nombre}.")
    elif solicitud.estado == SolicitudEmpleado.PENDIENTE:
        messages.info(request, f"Ya tienes una solicitud pendiente para {empresa.nombre}.")
    else:
        messages.success(request, f"Tu solicitud a {empresa.nombre} ya fue procesada.")

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
        empleados = CustomUser.objects.filter(role="EMPLEADO", empresa=request.user.empresa)
        return render(request, "chat_list.html", {"usuarios": empleados})

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
    if request.user.role != "EMPRESA":
        return redirect("producto_list")
    producto = get_object_or_404(Producto, pk=pk, empresa=request.user.empresa)
    if request.method == "POST":
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto actualizado correctamente.")
            return redirect("dashboard")
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
    busqueda_empresa = request.GET.get("empresa", "").strip()
    busqueda_categoria = request.GET.get("categoria", "").strip()
    busqueda_producto = request.GET.get("producto", "").strip()
    ensure_default_categorias()

    if request.user.is_authenticated and request.user.role == "EMPRESA":
        productos = Producto.objects.select_related("categoria", "proveedor", "empresa").filter(empresa=request.user.empresa).all()
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

        solicitudes_empresa = {
            item["empresa_id"]: item["estado"]
            for item in SolicitudEmpleado.objects.filter(empleado=request.user).values("empresa_id", "estado")
        }
        empresas_data = []
        for empresa in empresas:
            empresas_data.append({
                "empresa": empresa,
                "estado_solicitud": solicitudes_empresa.get(empresa.id),
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

    if request.method == "POST" and "contenido" in request.POST and "producto_id" in request.POST:
        if not request.user.is_authenticated:
            messages.warning(request, "Debes registrarte para comentar productos.")
            return redirect("register")

        if request.user.role == "EMPRESA":
            messages.warning(request, "La empresa no puede comentar productos.")
            return redirect("producto_list")

        product_id = request.POST.get("producto_id")
        producto = get_object_or_404(Producto, pk=product_id)
        form = ResenaForm(request.POST, initial={"autor": request.user})
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
        return render(request, "producto_list.html", {"productos": productos, "form": form, "busqueda_empresa": busqueda_empresa})

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
    reaccion, created = ReaccionResena.objects.get_or_create(resena=resena, usuario=request.user)
    reaccion.tipo = tipo
    reaccion.save()
    messages.success(request, "Tu reacción a la reseña fue registrada.")
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
def realizar_pedido(request, pk):
    if request.user.role == "EMPLEADO":
        messages.warning(request, "Los empleados no pueden comprar productos.")
        return redirect("producto_list")
    producto = get_object_or_404(Producto, pk=pk)
    if request.user.role != "CLIENTE":
        messages.warning(request, "Solo los clientes pueden comprar productos.")
        return redirect("producto_list")
    if producto.cantidad_stock <= 0:
        messages.error(request, "Este producto no tiene stock disponible.")
        return redirect("producto_list")
    if producto.cantidad_stock < 1:
        messages.error(request, "La cantidad solicitada supera el stock disponible.")
        return redirect("producto_list")

    producto.cantidad_stock -= 1
    producto.save()
    Movimiento.objects.create(
        producto=producto,
        tipo_movimiento=Movimiento.TIPO_SALIDA,
        cantidad=1,
        usuario=request.user,
        nota=f"Pedido realizado por {request.user.username}",
    )
    messages.success(request, f"Pedido realizado correctamente para {producto.nombre}.")
    return redirect("producto_list")
