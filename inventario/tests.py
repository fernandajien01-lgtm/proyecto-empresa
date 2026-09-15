from django.core import mail
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.contrib.auth.hashers import check_password
from django.utils import timezone
import re

from .forms import EmpresaForm, RegistroUsuarioForm, ResenaForm, SucursalForm
from .models import (
    Categoria,
    Carrito,
    CarritoItem,
    ChatMensaje,
    Empresa,
    Movimiento,
    Notificacion,
    Pedido,
    PedidoItem,
    Producto,
    Proveedor,
    Resena,
    SolicitudEmpleado,
    Sucursal,
)

User = get_user_model()


class ResenaFormTests(TestCase):
    def test_form_accepts_rating_and_content(self):
        form = ResenaForm(data={
            "calificacion": 5,
            "contenido": "Excelente producto.",
            "nombre_anonimo": "Cliente prueba",
        })

        self.assertTrue(form.is_valid(), form.errors)


class RegistroUsuarioFormTests(TestCase):
    def test_company_registration_accepts_optional_social_and_website_fields(self):
        form = RegistroUsuarioForm(data={
            "role": "EMPRESA",
            "username": "",
            "email": "empresa1@example.com",
            "first_name": "",
            "last_name": "",
            "nombre_empresa": "Mi tienda",
            "rif_empresa": "J-12345678",
            "descripcion_empresa": "Venta de productos",
            "telefono_empresa": "5551234",
            "direccion_empresa": "Calle 123",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_duplicate_username_is_rejected(self):
        # Create existing user
        User.objects.create_user(username="kfc", password="SecurePass123!")
        form = RegistroUsuarioForm(data={
            "username": "kfc",
            "email": "new@example.com",
            "first_name": "",
            "last_name": "",
            "role": "CLIENTE",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)


class EmpresaFormTests(TestCase):
    def test_company_form_allows_editing_contact_and_social_fields(self):
        form = EmpresaForm(data={
            "nombre": "Empresa editada",
            "descripcion": "Nueva descripción",
            "telefono": "5550000",
            "email": "contacto@empresa.com",
            "direccion": "Nueva dirección",
            "instagram": "@empresaeditada",
            "pagina_web": "https://empresaeditada.com",
        })

        self.assertTrue(form.is_valid(), form.errors)


class RegistroEmpleadoTests(TestCase):
    def test_empleado_registration_requires_cedula_telefono_residencia(self):
        form = RegistroUsuarioForm(data={
            "role": "EMPLEADO",
            "username": "",
            "email": "empleado1@example.com",
            "first_name": "Juan",
            "last_name": "Perez",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        self.assertFalse(form.is_valid())
        for campo in ("cedula", "telefono", "residencia"):
            self.assertIn(campo, form.errors)

    def test_empleado_registration_accepts_complete_employee_data(self):
        form = RegistroUsuarioForm(data={
            "role": "EMPLEADO",
            "username": "",
            "email": "empleado1@example.com",
            "first_name": "Juan",
            "last_name": "Perez",
            "cedula": "V-12345678",
            "telefono": "04121234567",
            "residencia": "Av. Principal #10",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.cedula, "V-12345678")
        self.assertEqual(user.telefono, "04121234567")
        self.assertEqual(user.residencia, "Av. Principal #10")
        self.assertEqual(user.username, "V12345678")

    def test_cedula_duplicate_is_rejected(self):
        User.objects.create_user(username="jose", password="SecurePass123!", role="EMPLEADO", cedula="V-12345678")
        form = RegistroUsuarioForm(data={
            "role": "EMPLEADO",
            "username": "",
            "email": "empleado2@example.com",
            "first_name": "Ana",
            "last_name": "Lopez",
            "cedula": "V-12345678",
            "telefono": "04121234567",
            "residencia": "Calle 5",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("cedula", form.errors)


class RegistroClienteTests(TestCase):
    def test_cliente_registration_stores_cedula_and_telefono(self):
        form = RegistroUsuarioForm(data={
            "role": "CLIENTE",
            "username": "pepito",
            "email": "cliente1@example.com",
            "first_name": "Pepe",
            "last_name": "Gonzalez",
            "cedula": "V-98765432",
            "telefono": "04140000000",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.role, "CLIENTE")
        self.assertEqual(user.cedula, "V-98765432")
        self.assertEqual(user.telefono, "04140000000")

    def test_cliente_registration_stores_fecha_nacimiento(self):
        form = RegistroUsuarioForm(data={
            "role": "CLIENTE",
            "username": "pepito",
            "email": "cliente2@example.com",
            "first_name": "Pepe",
            "last_name": "Gonzalez",
            "cedula": "V-11112222",
            "telefono": "04140000001",
            "fecha_nacimiento": "1995-06-15",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(str(user.fecha_nacimiento), "1995-06-15")

    def test_cliente_registration_rejects_year_out_of_range(self):
        form = RegistroUsuarioForm(data={
            "role": "CLIENTE",
            "username": "pepito",
            "email": "cliente3@example.com",
            "first_name": "Pepe",
            "last_name": "Gonzalez",
            "cedula": "V-33334444",
            "telefono": "04140000002",
            "fecha_nacimiento": "1920-06-15",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("fecha_nacimiento", form.errors)

    def test_cliente_registration_rejects_minor(self):
        hoy = timezone.localdate()
        nacimiento_menor = hoy.replace(year=hoy.year - 10)
        form = RegistroUsuarioForm(data={
            "role": "CLIENTE",
            "username": "menor",
            "email": "menor@example.com",
            "first_name": "Pepe",
            "last_name": "Gonzalez",
            "cedula": "V-55556666",
            "telefono": "04140000003",
            "fecha_nacimiento": nacimiento_menor.isoformat(),
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("fecha_nacimiento", form.errors)

    def test_cliente_registration_rejects_over_105(self):
        hoy = timezone.localdate()
        try:
            nacimiento_viejo = hoy.replace(year=hoy.year - 106)
        except ValueError:
            nacimiento_viejo = hoy.replace(year=hoy.year - 106, day=28)
        form = RegistroUsuarioForm(data={
            "role": "CLIENTE",
            "username": "abuelito",
            "email": "abuelito@example.com",
            "first_name": "Pepe",
            "last_name": "Gonzalez",
            "cedula": "V-77778888",
            "telefono": "04140000004",
            "fecha_nacimiento": nacimiento_viejo.isoformat(),
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("fecha_nacimiento", form.errors)


class ProductoListAccessTests(TestCase):
    def test_guest_comment_redirects_to_register(self):
        response = self.client.post(
            reverse("producto_list"),
            {"producto_id": 999, "contenido": "Comentario de invitado", "calificacion": 5},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("register"))

    def test_cliente_comment_is_saved_and_shown(self):
        empresa = Empresa.objects.create(
            nombre="Tienda TV", descripcion="Tienda", telefono="123", direccion="Calle 1"
        )
        categoria = Categoria.objects.create(nombre="Electrónica")
        proveedor = Proveedor.objects.create(
            nombre_negocio="Proveedor TV", telefono="555", email="tv@test.com", direccion="Dir"
        )
        producto = Producto.objects.create(
            nombre="Televisor OLED",
            descripcion="Televisor OLED 55 pulgadas",
            codigo_sku="SKU-TV001",
            categoria=categoria,
            proveedor=proveedor,
            empresa=empresa,
            precio_compra=800,
            precio_venta=1200,
            cantidad_stock=10,
            stock_minimo=1,
        )
        cliente = User.objects.create_user(
            username="comprador1", password="SecurePass123!", role="CLIENTE"
        )
        self.client.login(username="comprador1", password="SecurePass123!")

        response = self.client.post(
            reverse("producto_list"),
            {"producto_id": producto.pk, "contenido": "Excelente calidad", "calificacion": 5},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        resena = Resena.objects.filter(producto=producto).first()
        self.assertIsNotNone(resena)
        self.assertEqual(resena.autor, cliente)
        self.assertEqual(resena.contenido, "Excelente calidad")
        self.assertEqual(resena.calificacion, 5)
        self.assertEqual(producto.reseñas.count(), 1)


class ProductoEditPermissionsTests(TestCase):
    def test_employee_accepted_by_company_can_edit_products(self):
        empresa = Empresa.objects.create(
            nombre="Mi Empresa",
            descripcion="Empresa de prueba",
            telefono="123456",
            direccion="Calle 1",
        )
        empleado = User.objects.create_user(
            username="empleado1",
            password="SecurePass123!",
            role="EMPLEADO",
            empresa=empresa,
        )
        categoria = Categoria.objects.create(nombre="Ropa")
        proveedor = Proveedor.objects.create(
            nombre_negocio="Proveedor prueba",
            telefono="5550000",
            email="proveedor@test.com",
            direccion="Av. prueba 1",
        )
        producto = Producto.objects.create(
            nombre="Camisa",
            descripcion="Camisa prueba",
            codigo_sku="SKU-001",
            categoria=categoria,
            proveedor=proveedor,
            empresa=empresa,
            precio_compra=50,
            precio_venta=80,
            cantidad_stock=10,
            stock_minimo=2,
        )
        SolicitudEmpleado.objects.create(
            empleado=empleado,
            empresa=empresa,
            estado=SolicitudEmpleado.ACEPTADA,
        )

        # Use RequestFactory to call the view directly and avoid test client
        # template instrumentation that triggers copy/context issues on Python 3.14.
        from django.test import RequestFactory
        from django.contrib.auth import get_user_model
        from .views import producto_editar

        rf = RequestFactory()
        request = rf.get(f"/producto/{producto.pk}/editar/")
        request.user = empleado

        response = producto_editar(request, pk=producto.pk)

        # The view should return a 200 OK with the form for editing
        self.assertEqual(response.status_code, 200)


class MovimientoDeletionOnLeaveTests(TestCase):
    def test_movimientos_removed_when_employee_leaves(self):
        empresa = Empresa.objects.create(
            nombre="Empresa Movimiento",
            descripcion="Empresa test",
            telefono="123",
            direccion="Calle X",
        )
        empleado = User.objects.create_user(
            username="empleado_mov",
            password="testpass",
            role="EMPLEADO",
            empresa=empresa,
        )
        categoria = Categoria.objects.create(nombre="Varios")
        proveedor = Proveedor.objects.create(
            nombre_negocio="Prov",
            telefono="555",
            email="prov@test.com",
            direccion="Dir",
        )
        producto = Producto.objects.create(
            nombre="Item",
            descripcion="Item desc",
            codigo_sku="SKU-XYZ",
            categoria=categoria,
            proveedor=proveedor,
            empresa=empresa,
            precio_compra=10,
            precio_venta=15,
            cantidad_stock=20,
            stock_minimo=1,
        )
        Movimiento.objects.create(
            producto=producto,
            tipo_movimiento=Movimiento.TIPO_ENTRADA,
            cantidad=5,
            usuario=empleado,
        )

        # Precondition: movimiento exists
        self.assertEqual(Movimiento.objects.filter(usuario=empleado, producto__empresa=empresa).count(), 1)

        # Employee leaves the company
        logged_in = self.client.login(username="empleado_mov", password="testpass")
        self.assertTrue(logged_in)
        response = self.client.post(reverse("dejar_empresa"))

        # After leaving, movimientos for that employee and company should be removed
        self.assertEqual(Movimiento.objects.filter(usuario=empleado, producto__empresa=empresa).count(), 0)


@override_settings(
    DEBUG=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@example.com",
)
class PasswordResetTests(TestCase):
    def test_password_reset_sends_email_and_changes_password(self):
        user = User.objects.create_user(
            username="cliente_reset",
            email="cliente@example.com",
            password="OldSecurePass123!",
        )

        reset_form = PasswordResetForm(data={"email": "cliente@example.com"})
        self.assertTrue(reset_form.is_valid(), reset_form.errors)
        reset_form.save(
            domain_override="testserver",
            use_https=False,
            request=None,
            from_email="no-reply@example.com",
            email_template_name="password_reset_email.txt",
            subject_template_name="password_reset_subject.txt",
        )

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        reset_path = re.search(r"http://testserver(/recuperar-contrasena/\S+/\S+/)", message.body).group(1)

        uidb64, token = reset_path.strip("/").split("/")[-2:]
        self.assertTrue(uidb64)
        self.assertTrue(token)
        password_form = SetPasswordForm(
            user,
            data={
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            },
        )
        self.assertTrue(password_form.is_valid(), password_form.errors)
        password_form.save()
        user.refresh_from_db()
        self.assertTrue(check_password("NewSecurePass123!", user.password))


class CarritoCompraTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Tienda Test", descripcion="Desc", telefono="000", direccion="Calle 1")
        self.empresa_user = User.objects.create_user(username="empresaowner", password="p", role="EMPRESA", empresa=self.empresa)
        self.cliente = User.objects.create_user(username="comprador", password="p", role="CLIENTE")
        self.empleado = User.objects.create_user(username="empleado1", password="p", role="EMPLEADO", empresa=self.empresa)
        self.categoria = Categoria.objects.create(nombre="Varios")
        self.proveedor = Proveedor.objects.create(nombre_negocio="Prov", telefono="1", email="e@e.com", direccion="D")
        self.producto = Producto.objects.create(nombre="Producto A", descripcion="x", codigo_sku="SKU-A", categoria=self.categoria, proveedor=self.proveedor, empresa=self.empresa, precio_compra=50, precio_venta=100, cantidad_stock=10, stock_minimo=1)
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="Suc Central", direccion="Av 1", telefono="111", latitud="10.5", longitud="-66.9")

    def _login_cliente(self):
        self.assertTrue(self.client.login(username="comprador", password="p"))

    def test_agregar_y_quitar_carrito(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 2})
        item = CarritoItem.objects.get(carrito__cliente=self.cliente, producto=self.producto)
        self.assertEqual(item.cantidad, 2)
        self.client.post(reverse("carrito_quitar", args=[item.pk]))
        self.assertFalse(CarritoItem.objects.filter(pk=item.pk).exists())

    def test_actualizar_cantidad_carrito(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 1})
        item = CarritoItem.objects.get(carrito__cliente=self.cliente)
        self.client.post(reverse("carrito_actualizar", args=[item.pk]), {"cantidad": 5})
        item.refresh_from_db()
        self.assertEqual(item.cantidad, 5)

    def test_actualizar_cantidad_desde_checkout_vuelve_al_checkout(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 1})
        item = CarritoItem.objects.get(carrito__cliente=self.cliente)
        resp = self.client.post(
            reverse("carrito_actualizar", args=[item.pk]),
            {"cantidad": 4, "next": reverse("carrito_checkout")},
        )
        self.assertRedirects(resp, reverse("carrito_checkout"), fetch_redirect_response=False)
        item.refresh_from_db()
        self.assertEqual(item.cantidad, 4)

    def test_actualizar_no_acepta_redirect_externo(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 1})
        item = CarritoItem.objects.get(carrito__cliente=self.cliente)
        resp = self.client.post(
            reverse("carrito_actualizar", args=[item.pk]),
            {"cantidad": 3, "next": "https://evil.example/phish"},
        )
        self.assertRedirects(resp, reverse("carrito_detalle"), fetch_redirect_response=False)

    def test_quitar_desde_checkout_vuelve_al_checkout(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 2})
        item = CarritoItem.objects.get(carrito__cliente=self.cliente)
        resp = self.client.post(reverse("carrito_quitar", args=[item.pk]), {"next": reverse("carrito_checkout")})
        self.assertRedirects(resp, reverse("carrito_checkout"), fetch_redirect_response=False)
        self.assertFalse(CarritoItem.objects.filter(pk=item.pk).exists())

    def test_checkout_crea_pedido_y_vacia_carrito(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 2})
        response = self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "EFECTIVO",
            "direccion_entrega": "Casa 123",
            "sucursal_%d" % self.empresa.pk: self.sucursal.pk,
        })
        self.assertEqual(response.status_code, 302)
        pedido = Pedido.objects.get(cliente=self.cliente)
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)
        self.assertEqual(pedido.sucursal, self.sucursal)
        self.assertEqual(pedido.total, 200)
        self.assertEqual(pedido.items.count(), 1)
        self.assertEqual(pedido.items.first().cantidad, 2)
        self.assertFalse(CarritoItem.objects.filter(carrito__cliente=self.cliente).exists())
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad_stock, 10)

    def test_checkout_bloquea_sin_stock(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 2})
        self.producto.cantidad_stock = 1
        self.producto.save()
        response = self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "EFECTIVO",
            "direccion_entrega": "Casa 123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Pedido.objects.filter(cliente=self.cliente).exists())

    def test_checkout_notifica_a_empleados_de_la_empresa(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 2})
        self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "EFECTIVO",
            "direccion_entrega": "Casa 123",
        })
        pedido = Pedido.objects.get(cliente=self.cliente)
        notif = Notificacion.objects.get(usuario=self.empleado, pedido=pedido)
        self.assertEqual(notif.tipo, Notificacion.PEDIDO)
        self.assertFalse(notif.leida)
        self.assertIn(pedido.cliente.username, notif.mensaje)
        self.assertEqual(Notificacion.objects.filter(usuario=self.empleado, leida=False).count(), 1)

    def test_solo_empleados_de_esa_empresa_reciben_notificacion(self):
        otra_empresa = Empresa.objects.create(nombre="Otra", telefono="2", direccion="D2")
        otro_empleado = User.objects.create_user(username="empleado2", password="p", role="EMPLEADO", empresa=otra_empresa)
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 1})
        self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "TRANSFERENCIA",
            "direccion_entrega": "Casa 123",
        })
        self.assertEqual(Notificacion.objects.filter(usuario=self.empleado).count(), 1)
        self.assertEqual(Notificacion.objects.filter(usuario=otro_empleado).count(), 0)

    def test_pedidos_empleado_marca_notificaciones_como_leidas(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        from .views import pedidos_empleado
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 2})
        self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "EFECTIVO",
            "direccion_entrega": "Casa 123",
        })
        self.assertEqual(Notificacion.objects.filter(usuario=self.empleado, leida=False).count(), 1)
        rf = RequestFactory()
        request = rf.get(reverse("pedidos_empleado"))
        request.user = self.empleado
        request.session = {}
        request._messages = FallbackStorage(request)
        pedidos_empleado(request)
        self.assertEqual(Notificacion.objects.filter(usuario=self.empleado, leida=False).count(), 0)

    def test_empleado_procesa_pedido(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 2})
        self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "EFECTIVO",
            "direccion_entrega": "Casa 123",
        })
        pedido = Pedido.objects.get(cliente=self.cliente)
        self.assertTrue(self.client.login(username="empleado1", password="p"))
        response = self.client.post(reverse("procesar_pedido", args=[pedido.pk]))
        self.assertEqual(response.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.PROCESADO)
        self.assertEqual(pedido.empleado, self.empleado)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad_stock, 8)
        movimiento = Movimiento.objects.filter(producto=self.producto, tipo_movimiento=Movimiento.TIPO_SALIDA).first()
        self.assertIsNotNone(movimiento)
        self.assertEqual(movimiento.cantidad, 2)

    def test_empleado_otra_empresa_no_procesa(self):
        from django.http import Http404
        from django.test import RequestFactory
        from .views import procesar_pedido
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 1})
        self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "EFECTIVO",
            "direccion_entrega": "Casa 1",
        })
        pedido = Pedido.objects.get(cliente=self.cliente)
        otra = Empresa.objects.create(nombre="Otra", telefono="2", direccion="D")
        User.objects.create_user(username="otro_emp", password="p", role="EMPLEADO", empresa=otra)
        rf = RequestFactory()
        request = rf.post("/procesar/%d/" % pedido.pk)
        request.user = User.objects.get(username="otro_emp")
        with self.assertRaises(Http404):
            procesar_pedido(request, pk=pedido.pk)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)

    def test_empresa_marca_entregado_y_transicion_invalida(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 1})
        self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "TRANSFERENCIA",
            "direccion_entrega": "Casa 1",
        })
        pedido = Pedido.objects.get(cliente=self.cliente)
        self.assertTrue(self.client.login(username="empresaowner", password="p"))
        self.client.post(reverse("cambiar_estado_pedido", args=[pedido.pk, "ENTREGADO"]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)
        self.client.post(reverse("cambiar_estado_pedido", args=[pedido.pk, "CANCELADO"]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.CANCELADO)

    def test_sucursal_con_pedidos_bloqueada(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 1})
        self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "EFECTIVO",
            "direccion_entrega": "Casa 1",
            "sucursal_%d" % self.empresa.pk: self.sucursal.pk,
        })
        pedido = Pedido.objects.get(cliente=self.cliente)
        self.assertEqual(pedido.sucursal, self.sucursal)
        self.assertTrue(self.sucursal.tiene_pedidos)
        self.assertTrue(self.client.login(username="empresaowner", password="p"))
        self.client.post(reverse("sucursal_editar", args=[self.sucursal.pk]), {
            "nombre": "Nuevo nombre",
            "direccion": "Calle nueva",
            "telefono": "999",
        })
        self.sucursal.refresh_from_db()
        self.assertEqual(self.sucursal.nombre, "Suc Central")
        self.client.post(reverse("sucursal_eliminar", args=[self.sucursal.pk]))
        self.assertTrue(Sucursal.objects.filter(pk=self.sucursal.pk).exists())

    def test_sucursal_sin_pedidos_eliminable(self):
        self.assertTrue(self.client.login(username="empresaowner", password="p"))
        self.client.post(reverse("sucursal_eliminar", args=[self.sucursal.pk]))
        self.assertFalse(Sucursal.objects.filter(pk=self.sucursal.pk).exists())

    def test_chat_por_pedido_cliente_empleado(self):
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 1})
        self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "EFECTIVO",
            "direccion_entrega": "Casa 1",
        })
        pedido = Pedido.objects.get(cliente=self.cliente)
        self.assertTrue(self.client.login(username="empleado1", password="p"))
        self.client.post(reverse("procesar_pedido", args=[pedido.pk]))
        self.assertTrue(self.client.login(username="comprador", password="p"))
        response = self.client.post(reverse("pedido_detalle", args=[pedido.pk]), {
            "modo": "empleado",
            "mensaje": "Hola empleado, como va mi pedido?",
        })
        self.assertEqual(response.status_code, 302)
        msg = ChatMensaje.objects.get(pedido=pedido)
        self.assertEqual(msg.emisor, self.cliente)
        self.assertEqual(msg.receptor, self.empleado)
        self.assertEqual(msg.mensaje, "Hola empleado, como va mi pedido?")

    def test_pedido_detalle_permisos(self):
        from django.contrib.messages import get_messages
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        from .views import pedido_detalle
        self._login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.pk]), {"cantidad": 1})
        self.client.post(reverse("carrito_checkout"), {
            "metodo_pago": "EFECTIVO",
            "direccion_entrega": "Casa 1",
        })
        pedido = Pedido.objects.get(cliente=self.cliente)
        otro = User.objects.create_user(username="otro_cliente", password="p", role="CLIENTE")
        rf = RequestFactory()
        request = rf.get("/pedido/%d/" % pedido.pk)
        request.user = otro
        request.session = {}
        request._messages = FallbackStorage(request)
        response = pedido_detalle(request, pk=pedido.pk)
        self.assertEqual(response.status_code, 302)
        request = rf.get("/pedido/%d/" % pedido.pk)
        request.user = self.cliente
        response = pedido_detalle(request, pk=pedido.pk)
        self.assertEqual(response.status_code, 200)

    def test_movimiento_form_restringe_productos_a_empresa(self):
        from .forms import MovimientoForm
        otra = Empresa.objects.create(nombre="Otra", telefono="2", direccion="D")
        otro_prod = Producto.objects.create(
            nombre="Producto B",
            descripcion="x",
            codigo_sku="SKU-B",
            categoria=self.categoria,
            proveedor=self.proveedor,
            empresa=otra,
            precio_compra=10,
            precio_venta=20,
            cantidad_stock=5,
            stock_minimo=1,
        )
        form = MovimientoForm(
            data={"producto": otro_prod.pk, "tipo_movimiento": Movimiento.TIPO_ENTRADA, "cantidad": 5},
            user=self.empleado,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(Movimiento.objects.count(), 0)



class ReaccionResenaTests(TestCase):
    def setUp(self):
        self.cliente = User.objects.create_user(username="reactor", password="p", role="CLIENTE")
        self.cliente2 = User.objects.create_user(username="reactor2", password="p", role="CLIENTE")
        self.empresa = Empresa.objects.create(nombre="E", telefono="1", direccion="D")
        self.prod = Producto.objects.create(
            nombre="P", descripcion="x", codigo_sku="SKU-R1",
            categoria=Categoria.objects.create(nombre="Categoria R"),
            proveedor=Proveedor.objects.create(nombre_negocio="Prov R", telefono="1"),
            empresa=self.empresa,
            precio_compra=10, precio_venta=20, cantidad_stock=5, stock_minimo=1,
        )
        self.resena = Resena.objects.create(producto=self.prod, autor=self.cliente, calificacion=5, contenido="Bueno")

    def _reacciones(self):
        from .models import ReaccionResena
        likes = ReaccionResena.objects.filter(resena=self.resena, tipo=ReaccionResena.LIKE).count()
        dislikes = ReaccionResena.objects.filter(resena=self.resena, tipo=ReaccionResena.DISLIKE).count()
        return likes, dislikes

    def test_like_cambia_a_dislike_sin_duplicar(self):
        self.assertTrue(self.client.login(username="reactor", password="p"))
        self.client.post(reverse("reaccion_resena", args=[self.resena.pk, "LIKE"]))
        likes, dislikes = self._reacciones()
        self.assertEqual((likes, dislikes), (1, 0))
        self.client.post(reverse("reaccion_resena", args=[self.resena.pk, "DISLIKE"]))
        likes, dislikes = self._reacciones()
        self.assertEqual((likes, dislikes), (0, 1))

    def test_like_repetido_retira_reaccion(self):
        self.assertTrue(self.client.login(username="reactor", password="p"))
        self.client.post(reverse("reaccion_resena", args=[self.resena.pk, "LIKE"]))
        self.client.post(reverse("reaccion_resena", args=[self.resena.pk, "LIKE"]))
        likes, dislikes = self._reacciones()
        self.assertEqual((likes, dislikes), (0, 0))

    def test_conteos_separados_por_usuario(self):
        self.assertTrue(self.client.login(username="reactor", password="p"))
        self.client.post(reverse("reaccion_resena", args=[self.resena.pk, "LIKE"]))
        self.assertTrue(self.client.login(username="reactor2", password="p"))
        self.client.post(reverse("reaccion_resena", args=[self.resena.pk, "DISLIKE"]))
        likes, dislikes = self._reacciones()
        self.assertEqual((likes, dislikes), (1, 1))


class MovimientosHistorialTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Emp Mov", telefono="1", direccion="D")
        self.empresa_user = User.objects.create_user(username="dueno", password="p", role="EMPRESA", empresa=self.empresa)
        self.empleado1 = User.objects.create_user(username="emp1", password="p", role="EMPLEADO", empresa=self.empresa)
        self.empleado2 = User.objects.create_user(username="emp2", password="p", role="EMPLEADO", empresa=self.empresa)
        self.categoria = Categoria.objects.create(nombre="Cat Mov")
        self.proveedor = Proveedor.objects.create(nombre_negocio="Prov Mov", telefono="1")
        self.prod1 = Producto.objects.create(
            nombre="Prod 1", descripcion="x", codigo_sku="SKU-M1", categoria=self.categoria,
            proveedor=self.proveedor, empresa=self.empresa,
            precio_compra=10, precio_venta=20, cantidad_stock=10, stock_minimo=1,
        )
        self.prod2 = Producto.objects.create(
            nombre="Prod 2", descripcion="x", codigo_sku="SKU-M2", categoria=self.categoria,
            proveedor=self.proveedor, empresa=self.empresa,
            precio_compra=10, precio_venta=20, cantidad_stock=10, stock_minimo=1,
        )

    def _mov(self, usuario, producto, tipo, nota):
        return Movimiento.objects.create(
            producto=producto, tipo_movimiento=tipo, cantidad=3, usuario=usuario, nota=nota,
        )

    def _rf_get(self, url, usuario):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get(url)
        request.user = usuario
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_empleado_ve_solo_sus_movimientos_en_su_pestana(self):
        from .views import movimiento_crear
        self._mov(self.empleado1, self.prod1, Movimiento.TIPO_ENTRADA, nota="mov-uno")
        self._mov(self.empleado2, self.prod2, Movimiento.TIPO_SALIDA, nota="mov-dos")
        request = self._rf_get(reverse("movimiento_crear"), self.empleado1)
        response = movimiento_crear(request)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("mov-uno", content)
        self.assertNotIn("mov-dos", content)

    def test_empleado_filtra_su_historial_por_tipo(self):
        from .views import movimiento_crear
        self._mov(self.empleado1, self.prod1, Movimiento.TIPO_ENTRADA, nota="mov-entrada")
        self._mov(self.empleado1, self.prod2, Movimiento.TIPO_SALIDA, nota="mov-salida")
        request = self._rf_get(reverse("movimiento_crear") + "?tipo=ENTRADA", self.empleado1)
        response = movimiento_crear(request)
        content = response.content.decode()
        self.assertIn("mov-entrada", content)
        self.assertNotIn("mov-salida", content)

    def test_empleado_no_accede_a_gestion(self):
        from .views import movimientos_list
        request = self._rf_get(reverse("movimientos_list"), self.empleado1)
        response = movimientos_list(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    def test_empresa_ve_todos_los_movimientos_y_filtra(self):
        from .views import movimientos_list
        m1 = self._mov(self.empleado1, self.prod1, Movimiento.TIPO_ENTRADA, nota="mov-a")
        m2 = self._mov(self.empleado2, self.prod2, Movimiento.TIPO_SALIDA, nota="mov-b")
        request = self._rf_get(reverse("movimientos_list"), self.empresa_user)
        content = movimientos_list(request).content.decode()
        self.assertIn(m1.nota, content)
        self.assertIn(m2.nota, content)
        request = self._rf_get(
            reverse("movimientos_list") + "?empleado=%d" % self.empleado1.pk, self.empresa_user
        )
        content = movimientos_list(request).content.decode()
        self.assertIn(m1.nota, content)
        self.assertNotIn(m2.nota, content)
        request = self._rf_get(reverse("movimientos_list") + "?tipo=SALIDA", self.empresa_user)
        content = movimientos_list(request).content.decode()
        self.assertNotIn(m1.nota, content)
        self.assertIn(m2.nota, content)

    def test_empleado_se_queda_en_pestana_al_registrar(self):
        self.assertTrue(self.client.login(username="emp1", password="p"))
        resp = self.client.post(reverse("movimiento_crear"), {
            "producto": self.prod1.pk,
            "tipo_movimiento": "ENTRADA",
            "cantidad": 5,
            "nota": "",
        })
        self.assertRedirects(resp, reverse("movimiento_crear"), fetch_redirect_response=False)
        self.assertEqual(Movimiento.objects.filter(usuario=self.empleado1, producto=self.prod1).count(), 1)
