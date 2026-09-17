from django.core import mail
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.contrib.auth.hashers import check_password
from django.utils import timezone
import re

from .forms import EmpresaForm, RegistroUsuarioForm, ResenaForm
from .models import Categoria, Empresa, Producto, Proveedor, Resena, SolicitudEmpleado, Movimiento, CarritoItem, PedidoItem, Pedido, Notificacion, ChatMensaje, TokenEmpresa

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

    def test_reset_confirm_renderiza_ojo_en_campos_password(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "password_reset_confirm.html",
            {
                "validlink": True,
                "form": SetPasswordForm(user=User()),
            },
        )
        self.assertIn("id_new_password1", html)
        self.assertIn("id_new_password2", html)
        self.assertEqual(html.count("toggle-password"), 3)


class CarritoTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="TiendaCarrito", descripcion="Tienda", telefono="123", direccion="Dir"
        )
        self.empresa2 = Empresa.objects.create(
            nombre="Tienda2", descripcion="Tienda 2", telefono="456", direccion="Dir 2"
        )
        self.categoria = Categoria.objects.create(nombre="Electrónica")
        self.proveedor = Proveedor.objects.create(
            nombre_negocio="ProvCarrito", telefono="555", email="prov@test.com", direccion="Dir"
        )
        self.producto = Producto.objects.create(
            nombre="Monitor",
            descripcion="Monitor 27 pulgadas",
            codigo_sku="SKU-MON01",
            categoria=self.categoria,
            proveedor=self.proveedor,
            empresa=self.empresa,
            precio_compra=200,
            precio_venta=350,
            cantidad_stock=10,
            stock_minimo=1,
        )
        self.producto2 = Producto.objects.create(
            nombre="Teclado",
            descripcion="Teclado mecánico",
            codigo_sku="SKU-TEC02",
            categoria=self.categoria,
            proveedor=self.proveedor,
            empresa=self.empresa2,
            precio_compra=30,
            precio_venta=60,
            cantidad_stock=5,
            stock_minimo=1,
        )
        self.cliente = User.objects.create_user(
            username="carrito_cliente", password="testpass", role="CLIENTE"
        )
        self.empleado = User.objects.create_user(
            username="carrito_empleado", password="testpass", role="EMPLEADO"
        )
        self.empleado.empresa = self.empresa
        self.empleado.save()
        self.empresa_users = []
        for i, emp in enumerate((self.empresa, self.empresa2)):
            u = User.objects.create_user(
                username=f"empresa_user_{i}", password="testpass", role="EMPRESA"
            )
            u.empresa = emp
            u.save()
            self.empresa_users.append(u)

    def login_cliente(self):
        self.client.login(username="carrito_cliente", password="testpass")

    def login_empleado(self):
        self.client.login(username="carrito_empleado", password="testpass")

    def test_cliente_agrega_item_al_carrito(self):
        self.login_cliente()
        response = self.client.post(reverse("carrito_agregar", args=[self.producto.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("carrito_detalle"))
        self.assertEqual(CarritoItem.objects.count(), 1)

    def test_agregar_item_repetido_suma_cantidades(self):
        self.login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.id]))
        self.client.post(reverse("carrito_agregar", args=[self.producto.id]))
        item = CarritoItem.objects.get()
        self.assertEqual(item.cantidad, 2)

    def test_agregar_con_cantidad_personalizada(self):
        self.login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.id]), {"cantidad": 4})
        item = CarritoItem.objects.get()
        self.assertEqual(item.cantidad, 4)

    def test_actualizar_cantidades(self):
        self.login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.id]))
        item = CarritoItem.objects.get()
        self.client.post(reverse("carrito_actualizar", args=[item.id]), {"cantidad": 3})
        item.refresh_from_db()
        self.assertEqual(item.cantidad, 3)

    def test_quitar_item(self):
        self.login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.id]))
        item = CarritoItem.objects.get()
        self.client.post(reverse("carrito_quitar", args=[item.id]))
        self.assertEqual(CarritoItem.objects.count(), 0)

    def _checkout(self, cantidad=1, metodo="TRANSFERENCIA", direccion="Av Principal 123"):
        self.client.post(reverse("carrito_agregar", args=[self.producto.id]), {"cantidad": cantidad})
        return self.client.post(
            reverse("carrito_checkout"),
            {"metodo_pago": metodo, "direccion_entrega": direccion},
        )

    def test_checkout_crea_pedido_pendiente_sin_descontar_stock(self):
        self.login_cliente()
        response = self._checkout(cantidad=2)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("mis_pedidos"))

        pedido = Pedido.objects.get()
        self.assertEqual(pedido.cliente, self.cliente)
        self.assertEqual(pedido.empresa, self.empresa)
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)
        self.assertEqual(pedido.metodo_pago, "TRANSFERENCIA")
        self.assertEqual(pedido.direccion_entrega, "Av Principal 123")
        self.assertEqual(pedido.total, 700)
        self.assertEqual(PedidoItem.objects.filter(pedido=pedido).count(), 1)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad_stock, 10)
        self.assertEqual(CarritoItem.objects.count(), 0)
        self.assertEqual(
            Notificacion.objects.filter(usuario=self.empleado, pedido=pedido, leida=False).count(),
            1,
        )

    def test_checkout_agrupa_pedidos_por_empresa(self):
        self.login_cliente()
        self.client.post(reverse("carrito_agregar", args=[self.producto.id]))
        self.client.post(reverse("carrito_agregar", args=[self.producto2.id]))
        self.client.post(reverse("carrito_checkout"), {"metodo_pago": "EFECTIVO", "direccion_entrega": "Centro"})
        self.assertEqual(Pedido.objects.count(), 2)
        self.assertEqual(
            set(Pedido.objects.values_list("empresa_id", flat=True)),
            {self.empresa.id, self.empresa2.id},
        )
        self.assertEqual(CarritoItem.objects.count(), 0)

    def test_checkout_stock_insuficiente(self):
        self.login_cliente()
        self._checkout(cantidad=50)
        self.assertEqual(Pedido.objects.count(), 0)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad_stock, 10)
        self.assertEqual(CarritoItem.objects.count(), 1)

    def test_empleado_no_puede_usar_carrito(self):
        self.login_empleado()
        response = self.client.get(reverse("carrito_detalle"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("producto_list"))

    def test_invitado_es_redirigido_a_login(self):
        response = self.client.get(reverse("carrito_detalle"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_procesar_pedido_descuenta_stock(self):
        self.login_cliente()
        self._checkout(cantidad=2)
        pedido = Pedido.objects.get()

        self.login_empleado()
        self.client.post(reverse("tomar_pedido", args=[pedido.id]))
        response = self.client.post(reverse("procesar_pedido", args=[pedido.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("pedidos_empleado"))

        pedido.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.PROCESADO)
        self.assertEqual(pedido.empleado, self.empleado)
        self.assertEqual(self.producto.cantidad_stock, 8)
        self.assertTrue(
            Movimiento.objects.filter(
                producto=self.producto, tipo_movimiento=Movimiento.TIPO_SALIDA, cantidad=2
            ).exists()
        )

    def test_procesar_pedido_sin_stock(self):
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            empresa=self.empresa,
            metodo_pago=Pedido.EFECTIVO,
            total=17500,
        )
        PedidoItem.objects.create(pedido=pedido, producto=self.producto, cantidad=50, precio=350)
        self.login_empleado()
        self.client.post(reverse("tomar_pedido", args=[pedido.id]))
        response = self.client.post(reverse("procesar_pedido", args=[pedido.id]))
        self.assertEqual(response.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad_stock, 10)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)
        self.assertFalse(Movimiento.objects.filter(producto=self.producto).exists())

    def test_cambiar_estado_pedido_validaciones(self):
        self.login_cliente()
        self._checkout(cantidad=1)
        pedido = Pedido.objects.get()
        self.login_empleado()
        self.client.post(reverse("tomar_pedido", args=[pedido.id]))
        self.client.post(reverse("procesar_pedido", args=[pedido.id]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.PROCESADO)

        response = self.client.post(reverse("cambiar_estado_pedido", args=[pedido.id, "ENTREGADO"]))
        self.assertEqual(response.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.ENTREGADO)

        self.client.post(reverse("cambiar_estado_pedido", args=[pedido.id, "CANCELADO"]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.ENTREGADO)

    def test_empresa_puede_supervisar_pedidos(self):
        self.login_cliente()
        self._checkout()
        self.client.logout()
        self.client.login(username="empresa_user_0", password="testpass")
        self.client.post(reverse("cambiar_estado_pedido", args=[Pedido.objects.get().id, "CANCELADO"]))
        self.assertEqual(Pedido.objects.get().estado, Pedido.CANCELADO)

    def test_chat_del_pedido_crea_mensaje(self):
        self.login_cliente()
        self._checkout()
        self.login_empleado()
        pedido = Pedido.objects.get()
        self.client.post(reverse("tomar_pedido", args=[pedido.id]))
        self.client.post(reverse("procesar_pedido", args=[pedido.id]))
        pedido.refresh_from_db()

        self.login_cliente()
        self.client.post(
            reverse("pedido_detalle", args=[pedido.id]),
            {"modo": "empleado", "mensaje": "Hola, ¿cuándo llega?"},
        )
        self.assertEqual(ChatMensaje.objects.filter(pedido=pedido).count(), 1)

    def test_badge_contador_en_navbar(self):
        from django.test import RequestFactory
        from inventario.context_processors import carrito_count, notificaciones_empleado

        request = RequestFactory().get("/")
        request.user = self.cliente
        CarritoItem.objects.create(usuario=self.cliente, producto=self.producto, cantidad=3)
        self.assertEqual(carrito_count(request)["carrito_count"], 3)

        request.user = self.empleado
        self.assertEqual(carrito_count(request)["carrito_count"], 0)

        Notificacion.objects.create(
            usuario=self.empleado, tipo=Notificacion.PEDIDO, titulo="Nuevo pedido"
        )
        request.user = self.empleado
        self.assertEqual(notificaciones_empleado(request)["notificaciones_no_leidas"], 1)


class PedidosDisponiblesTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="EmpresaCercania", descripcion="Test", telefono="123", direccion="Dir"
        )
        self.empresa2 = Empresa.objects.create(
            nombre="OtraEmpresa", descripcion="Test 2", telefono="456", direccion="Dir 2"
        )
        self.categoria = Categoria.objects.create(nombre="Varios")
        self.proveedor = Proveedor.objects.create(
            nombre_negocio="ProvCercania", telefono="555", email="prov@test.com", direccion="Dir"
        )
        self.producto = Producto.objects.create(
            nombre="Artículo",
            descripcion="Desc",
            codigo_sku="SKU-CER01",
            categoria=self.categoria,
            proveedor=self.proveedor,
            empresa=self.empresa,
            precio_compra=10,
            precio_venta=20,
            cantidad_stock=10,
            stock_minimo=1,
        )
        self.cliente = User.objects.create_user(
            username="cliente_cercania", password="testpass", role="CLIENTE"
        )
        self.empleado = User.objects.create_user(
            username="empleado_cercania", password="testpass", role="EMPLEADO"
        )
        self.empleado.empresa = self.empresa
        self.empleado.save()
        self.empleado2 = User.objects.create_user(
            username="empleado_otro", password="testpass", role="EMPLEADO"
        )
        self.empleado2.empresa = self.empresa
        self.empleado2.save()
        self.empresa_user = User.objects.create_user(
            username="empresa_cercania", password="testpass", role="EMPRESA"
        )
        self.empresa_user.empresa = self.empresa
        self.empresa_user.save()

    def _pedido(self, lat=None, lon=None, empleado=None, estado=None):
        return Pedido.objects.create(
            cliente=self.cliente,
            empresa=self.empresa,
            metodo_pago=Pedido.EFECTIVO,
            total=20,
            latitud=lat,
            longitud=lon,
            empleado=empleado,
            estado=estado or Pedido.PENDIENTE,
        )

    def test_tomar_pedido_asigna_empleado(self):
        pedido = self._pedido(lat=10.5, lon=-66.9)
        self.client.login(username="empleado_cercania", password="testpass")
        response = self.client.post(reverse("tomar_pedido", args=[pedido.id]))
        self.assertEqual(response.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.empleado, self.empleado)
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)

    @override_settings(DEBUG=False)
    def test_tomar_pedido_solo_del_pool(self):
        from django.http import Http404
        from django.test import RequestFactory
        from inventario.views import tomar_pedido

        pedido = self._pedido(empleado=self.empleado2)
        rf = RequestFactory()
        request = rf.post(reverse("tomar_pedido", args=[pedido.id]))
        request.user = self.empleado
        with self.assertRaises(Http404):
            tomar_pedido(request, pk=pedido.id)
        pedido.refresh_from_db()
        self.assertEqual(pedido.empleado, self.empleado2)

    def test_limite_7_pedidos_a_cargo(self):
        for _ in range(7):
            self._pedido(lat=10.5, lon=-66.9, empleado=self.empleado)
        libre = self._pedido(lat=10.5, lon=-66.9)
        self.client.login(username="empleado_cercania", password="testpass")
        response = self.client.post(reverse("tomar_pedido", args=[libre.id]))
        self.assertEqual(response.status_code, 302)
        libre.refresh_from_db()
        self.assertIsNone(libre.empleado)

    def test_pedidos_entregados_no_cuentan_para_el_limite(self):
        for _ in range(7):
            self._pedido(lat=10.5, lon=-66.9, empleado=self.empleado, estado=Pedido.ENTREGADO)
        libre = self._pedido(lat=10.5, lon=-66.9)
        self.client.login(username="empleado_cercania", password="testpass")
        response = self.client.post(reverse("tomar_pedido", args=[libre.id]))
        self.assertEqual(response.status_code, 302)
        libre.refresh_from_db()
        self.assertEqual(libre.empleado, self.empleado)

    def test_limite_cuenta_pendientes_y_procesados(self):
        for estado in (Pedido.PENDIENTE, Pedido.PROCESADO):
            self._pedido(lat=10.5, lon=-66.9, empleado=self.empleado, estado=estado)
        self.assertEqual(
            Pedido.objects.filter(
                empleado=self.empleado, estado__in=[Pedido.PENDIENTE, Pedido.PROCESADO]
            ).count(),
            2,
        )

    def test_procesar_pedido_requiere_ser_el_dueño(self):
        pedido = self._pedido(lat=10.5, lon=-66.9)
        self.client.login(username="empleado_otro", password="testpass")
        self.client.post(reverse("tomar_pedido", args=[pedido.id]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.empleado, self.empleado2)

        self.client.logout()
        self.client.login(username="empleado_cercania", password="testpass")
        response = self.client.post(reverse("procesar_pedido", args=[pedido.id]))
        self.assertEqual(response.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.empleado, self.empleado2)
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad_stock, 10)

    def test_liberar_pedido_vuelve_a_la_lista_y_notifica(self):
        pedido = self._pedido(lat=10.5, lon=-66.9, empleado=self.empleado)
        self.client.login(username="empleado_cercania", password="testpass")
        response = self.client.post(
            reverse("liberar_pedido", args=[pedido.id]), {"motivo": "El producto no está disponible"}
        )
        self.assertEqual(response.status_code, 302)
        pedido.refresh_from_db()
        self.assertIsNone(pedido.empleado)
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)
        notificados = set(
            Notificacion.objects.filter(
                tipo=Notificacion.PEDIDO, pedido=pedido, mensaje__icontains="El producto no está disponible"
            ).values_list("usuario_id", flat=True)
        )
        self.assertEqual(notificados, {self.cliente.id, self.empresa_user.id})

    def test_liberar_pedido_requiere_motivo(self):
        pedido = self._pedido(lat=10.5, lon=-66.9, empleado=self.empleado)
        self.client.login(username="empleado_cercania", password="testpass")
        response = self.client.post(reverse("liberar_pedido", args=[pedido.id]), {"motivo": ""})
        self.assertEqual(response.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.empleado, self.empleado)
        self.assertEqual(Notificacion.objects.filter(usuario=self.cliente).count(), 0)

    def test_guardar_ubicacion(self):
        self.client.login(username="empleado_cercania", password="testpass")
        response = self.client.post(
            reverse("guardar_ubicacion"), {"latitud": "10.4805937", "longitud": "-66.9036063"}
        )
        self.assertEqual(response.status_code, 302)
        self.empleado.refresh_from_db()
        self.assertEqual(float(self.empleado.latitud), 10.480594)
        self.assertEqual(float(self.empleado.longitud), -66.903606)

    def test_guardar_ubicacion_invalida(self):
        self.client.login(username="empleado_cercania", password="testpass")
        self.client.post(reverse("guardar_ubicacion"), {"latitud": "999", "longitud": "-66.9"})
        self.empleado.refresh_from_db()
        self.assertIsNone(self.empleado.latitud)


class PedidosAccesoTests(TestCase):
    def setUp(self):
        from inventario.views import _clasificar_disponibles, _pedido_visible_para

        self.empresa = Empresa.objects.create(
            nombre="AccesoEmpresa", descripcion="Test", telefono="123", direccion="Dir"
        )
        self.empresa2 = Empresa.objects.create(
            nombre="AccesoOtra", descripcion="Test 2", telefono="456", direccion="Dir 2"
        )
        self.cliente = User.objects.create_user(
            username="cliente_acceso", password="testpass", role="CLIENTE"
        )
        self.otro_cliente = User.objects.create_user(
            username="cliente_acceso2", password="testpass", role="CLIENTE"
        )
        self.empleado = User.objects.create_user(
            username="empleado_acceso", password="testpass", role="EMPLEADO"
        )
        self.empleado.empresa = self.empresa
        self.empleado.save()
        self.otro_empleado = User.objects.create_user(
            username="empleado_externo", password="testpass", role="EMPLEADO"
        )
        self.otro_empleado.empresa = self.empresa2
        self.otro_empleado.save()
        self.empresa_user = User.objects.create_user(
            username="empresa_acceso", password="testpass", role="EMPRESA"
        )
        self.empresa_user.empresa = self.empresa
        self.empresa_user.save()
        self.otra_empresa_user = User.objects.create_user(
            username="empresa_externa", password="testpass", role="EMPRESA"
        )
        self.otra_empresa_user.empresa = self.empresa2
        self.otra_empresa_user.save()

    def _pedido(self):
        return Pedido.objects.create(
            cliente=self.cliente,
            empresa=self.empresa,
            metodo_pago=Pedido.EFECTIVO,
            total=10,
        )

    def test_visibilidad_del_pedido_por_rol(self):
        from inventario.views import _pedido_visible_para

        pedido = self._pedido()
        self.assertTrue(_pedido_visible_para(self.cliente, pedido))
        self.assertTrue(_pedido_visible_para(self.empleado, pedido))
        self.assertTrue(_pedido_visible_para(self.empresa_user, pedido))
        self.assertFalse(_pedido_visible_para(self.otro_cliente, pedido))
        self.assertFalse(_pedido_visible_para(self.otro_empleado, pedido))
        self.assertFalse(_pedido_visible_para(self.otra_empresa_user, pedido))

    def test_clasificar_disponibles_por_distancia(self):
        from inventario.views import _clasificar_disponibles

        e_lat, e_lon = 10.5, -66.9
        cerca1 = self._pedido()
        cerca1.latitud = 10.501
        cerca1.longitud = -66.9
        fuera = self._pedido()
        fuera.latitud = 40.0
        fuera.longitud = -66.9
        sin_coords = self._pedido()
        pedidos = [fuera, sin_coords, cerca1]
        cerca, otros = _clasificar_disponibles(pedidos, e_lat, e_lon, 10)
        self.assertIn(cerca1, cerca)
        self.assertTrue(hasattr(cerca1, "distancia_km"))
        self.assertLess(cerca1.distancia_km, 1)
        self.assertIn(fuera, otros)
        self.assertIn(sin_coords, otros)
        self.assertEqual(len(cerca) + len(otros), len(pedidos))

    def test_clasificar_sin_ubicacion_del_empleado(self):
        from inventario.views import _clasificar_disponibles

        cerca1 = self._pedido()
        cerca1.latitud = 10.501
        cerca1.longitud = -66.9
        cerca, otros = _clasificar_disponibles([cerca1], None, None, 10)
        self.assertEqual(cerca, [])
        self.assertIn(cerca1, otros)


class ProductoAprobacionTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="AprobarSA", descripcion="Test", telefono="123", direccion="Dir"
        )
        self.empresa2 = Empresa.objects.create(
            nombre="OtraSA", descripcion="Test 2", telefono="456", direccion="Dir 2"
        )
        self.categoria = Categoria.objects.create(nombre="General")
        self.proveedor = Proveedor.objects.create(
            nombre_negocio="ProvAprob", telefono="555", email="p@test.com", direccion="Dir"
        )
        self.empleado = User.objects.create_user(
            username="emp_aprob", password="testpass", role="EMPLEADO"
        )
        self.empleado.empresa = self.empresa
        self.empleado.save()
        SolicitudEmpleado.objects.create(
            empleado=self.empleado, empresa=self.empresa, estado=SolicitudEmpleado.ACEPTADA
        )
        self.empresa_user = User.objects.create_user(
            username="empresa_aprob", password="testpass", role="EMPRESA"
        )
        self.empresa_user.empresa = self.empresa
        self.empresa_user.save()
        self.otra_empresa_user = User.objects.create_user(
            username="empresa_otra", password="testpass", role="EMPRESA"
        )
        self.otra_empresa_user.empresa = self.empresa2
        self.otra_empresa_user.save()
        self.empleado_otra = User.objects.create_user(
            username="emp_otra", password="testpass", role="EMPLEADO"
        )
        self.empleado_otra.empresa = self.empresa2
        self.empleado_otra.save()
        self.cliente = User.objects.create_user(
            username="cliente_aprob", password="testpass", role="CLIENTE"
        )

    def _producto(self, estado=Producto.APROBADO, creador=None, nombre="Producto prueba"):
        return Producto.objects.create(
            nombre=nombre,
            descripcion="Desc",
            codigo_sku=f"SKU-PROD{Producto.objects.count()+1}-APR",
            categoria=self.categoria,
            proveedor=self.proveedor,
            empresa=self.empresa,
            precio_compra=5,
            precio_venta=10,
            cantidad_stock=10,
            stock_minimo=1,
            estado=estado,
            creado_por=creador,
        )

    def _data_crear(self):
        return {
            "nombre": "Nuevo producto",
            "descripcion": "Descripción nueva",
            "categoria": self.categoria.id,
            "precio_venta": "25.00",
            "cantidad_stock": "5",
            "stock_minimo": "1",
        }

    def test_empleado_crea_producto_pendiente_y_notifica_empresa(self):
        self.client.login(username="emp_aprob", password="testpass")
        response = self.client.post(reverse("producto_crear"), self._data_crear())
        self.assertEqual(response.status_code, 302)
        producto = Producto.objects.get(nombre="Nuevo producto")
        self.assertEqual(producto.estado, Producto.PENDIENTE)
        self.assertEqual(producto.creado_por, self.empleado)
        self.assertTrue(
            Notificacion.objects.filter(usuario=self.empresa_user, tipo=Notificacion.PRODUCTO).exists()
        )

    def test_empresa_crea_producto_aprobado(self):
        self.client.login(username="empresa_aprob", password="testpass")
        response = self.client.post(reverse("producto_crear"), self._data_crear())
        self.assertEqual(response.status_code, 302)
        producto = Producto.objects.get(nombre="Nuevo producto")
        self.assertEqual(producto.estado, Producto.APROBADO)

    def test_empresa_aprueba_producto_pendiente(self):
        producto = self._producto(estado=Producto.PENDIENTE, creador=self.empleado)
        self.client.login(username="empresa_aprob", password="testpass")
        response = self.client.post(reverse("aprobar_producto", args=[producto.id, "aprobar"]))
        self.assertEqual(response.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.estado, Producto.APROBADO)
        notif = Notificacion.objects.filter(
            usuario=self.empleado, tipo=Notificacion.PRODUCTO, mensaje__icontains="aprobó"
        )
        self.assertTrue(notif.exists())

    def test_empresa_rechaza_producto_pendiente_con_motivo(self):
        producto = self._producto(estado=Producto.PENDIENTE, creador=self.empleado)
        self.client.login(username="empresa_aprob", password="testpass")
        response = self.client.post(
            reverse("aprobar_producto", args=[producto.id, "rechazar"]),
            {"motivo": "Imagen borrosa"},
        )
        self.assertEqual(response.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.estado, Producto.RECHAZADO)
        notif = Notificacion.objects.filter(
            usuario=self.empleado, tipo=Notificacion.PRODUCTO, mensaje__icontains="Imagen borrosa"
        )
        self.assertTrue(notif.exists())

    def test_solo_empresa_puede_aprobar(self):
        producto = self._producto(estado=Producto.PENDIENTE, creador=self.empleado)
        self.client.login(username="emp_aprob", password="testpass")
        response = self.client.post(reverse("aprobar_producto", args=[producto.id, "aprobar"]))
        self.assertEqual(response.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.estado, Producto.PENDIENTE)

    def test_otra_empresa_no_puede_aprobar_ajena(self):
        from django.http import Http404
        from django.test import RequestFactory
        from inventario.views import aprobar_producto

        producto = self._producto(estado=Producto.PENDIENTE, creador=self.empleado)
        rf = RequestFactory()
        request = rf.post(reverse("aprobar_producto", args=[producto.id, "aprobar"]))
        request.user = self.otra_empresa_user
        with self.assertRaises(Http404):
            aprobar_producto(request, pk=producto.id, accion="aprobar")
        producto.refresh_from_db()
        self.assertEqual(producto.estado, Producto.PENDIENTE)

    def test_empleado_edita_aprobado_y_vuelve_a_pendiente(self):
        producto = self._producto(estado=Producto.APROBADO, creador=self.empleado)
        self.client.login(username="emp_aprob", password="testpass")
        response = self.client.post(reverse("producto_editar", args=[producto.id]), self._data_crear())
        self.assertEqual(response.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.estado, Producto.PENDIENTE)
        self.assertTrue(
            Notificacion.objects.filter(usuario=self.empresa_user, tipo=Notificacion.PRODUCTO).exists()
        )

    def test_empleado_edita_rechazado_y_reenvia_a_pendiente(self):
        producto = self._producto(estado=Producto.RECHAZADO, creador=self.empleado, nombre="Corregido")
        self.client.login(username="emp_aprob", password="testpass")
        data = self._data_crear()
        data["nombre"] = "Corregido"
        response = self.client.post(reverse("producto_editar", args=[producto.id]), data)
        self.assertEqual(response.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.estado, Producto.PENDIENTE)

    def test_empresa_edita_pendiente_y_queda_aprobado(self):
        producto = self._producto(estado=Producto.PENDIENTE, creador=self.empleado, nombre="Directo")
        self.client.login(username="empresa_aprob", password="testpass")
        data = self._data_crear()
        data["nombre"] = "Directo"
        response = self.client.post(reverse("producto_editar", args=[producto.id]), data)
        self.assertEqual(response.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.estado, Producto.APROBADO)

    def test_carrito_agregar_producto_pendiente_rechazado(self):
        from django.http import Http404
        from django.test import RequestFactory
        from inventario.views import carrito_agregar

        producto = self._producto(estado=Producto.PENDIENTE)
        rf = RequestFactory()
        request = rf.post(reverse("carrito_agregar", args=[producto.id]), {"cantidad": "1"})
        request.user = self.cliente
        with self.assertRaises(Http404):
            carrito_agregar(request, pk=producto.id)
        self.assertEqual(CarritoItem.objects.count(), 0)

    def test_realizar_pedido_producto_pendiente_rechazado(self):
        from django.http import Http404
        from django.test import RequestFactory
        from inventario.views import realizar_pedido

        producto = self._producto(estado=Producto.PENDIENTE)
        rf = RequestFactory()
        request = rf.get(reverse("realizar_pedido", args=[producto.id]))
        request.user = self.cliente
        with self.assertRaises(Http404):
            realizar_pedido(request, pk=producto.id)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_producto_pendiente_no_visible_para_cliente(self):
        from django.test import RequestFactory
        from inventario.views import producto_list

        self._producto(estado=Producto.APROBADO, nombre="Visible aprobado")
        self._producto(estado=Producto.PENDIENTE, nombre="Oculto pendiente")
        rf = RequestFactory()
        request = rf.get(reverse("producto_list"))
        request.user = self.cliente
        response = producto_list(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible aprobado")
        self.assertNotContains(response, "Oculto pendiente")

    def test_campana_notificaciones_tambien_para_empresa(self):
        from django.test import RequestFactory
        from inventario.context_processors import notificaciones_empleado

        Notificacion.objects.create(
            usuario=self.empresa_user,
            tipo=Notificacion.PRODUCTO,
            titulo="Producto por aprobar",
            mensaje="Revisa el dashboard.",
        )
        request = RequestFactory().get("/")
        request.user = self.empresa_user
        ctx = notificaciones_empleado(request)
        self.assertEqual(ctx["notificaciones_no_leidas"], 1)

        request.user = self.cliente
        self.assertEqual(notificaciones_empleado(request)["notificaciones_no_leidas"], 0)


class CategoriaGestionTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="CatSA", descripcion="Test", telefono="123", direccion="Dir"
        )
        self.categoria_v = Categoria.objects.create(nombre="Varios")
        self.empleado = User.objects.create_user(
            username="emp_cat", password="testpass", role="EMPLEADO"
        )
        self.empleado.empresa = self.empresa
        self.empleado.save()
        SolicitudEmpleado.objects.create(
            empleado=self.empleado, empresa=self.empresa, estado=SolicitudEmpleado.ACEPTADA
        )
        self.empresa_user = User.objects.create_user(
            username="empresa_cat", password="testpass", role="EMPRESA"
        )
        self.empresa_user.empresa = self.empresa
        self.empresa_user.save()
        self.cliente = User.objects.create_user(
            username="cliente_cat", password="testpass", role="CLIENTE"
        )
        self.proveedor = Proveedor.objects.create(
            nombre_negocio="ProvCat", telefono="555", email="c@test.com", direccion="Dir"
        )

    def test_empleado_puede_crear_categoria(self):
        self.client.login(username="emp_cat", password="testpass")
        response = self.client.post(
            reverse("categoria_crear"), {"nombre": "Deportes", "descripcion": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Categoria.objects.filter(nombre="Deportes").exists())

    def test_empleado_puede_editar_categoria(self):
        self.client.login(username="emp_cat", password="testpass")
        response = self.client.post(
            reverse("categoria_editar", args=[self.categoria_v.id]),
            {"nombre": "Hogar", "descripcion": "Electrodomésticos"},
        )
        self.assertEqual(response.status_code, 302)
        self.categoria_v.refresh_from_db()
        self.assertEqual(self.categoria_v.nombre, "Hogar")

    def test_empresa_puede_crear_categoria(self):
        self.client.login(username="empresa_cat", password="testpass")
        response = self.client.post(
            reverse("categoria_crear"), {"nombre": "Artesanías", "descripcion": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Categoria.objects.filter(nombre="Artesanías").exists())

    def test_cliente_no_puede_gestionar_categorias(self):
        self.client.login(username="cliente_cat", password="testpass")
        response = self.client.post(
            reverse("categoria_crear"), {"nombre": "Robots", "descripcion": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Categoria.objects.filter(nombre="Robots").exists())

    def test_gestionar_categorias_render_para_empleado(self):
        from django.test import RequestFactory
        from inventario.views import gestionar_categorias

        rf = RequestFactory()
        request = rf.get(reverse("gestionar_categorias"))
        request.user = self.empleado
        response = gestionar_categorias(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Varios")

    def test_nueva_categoria_al_crear_producto(self):
        self.client.login(username="emp_cat", password="testpass")
        response = self.client.post(
            reverse("producto_crear"),
            {
                "nombre": "Balón de fútbol",
                "descripcion": "Balón profesional",
                "categoria": "",
                "precio_venta": "30.00",
                "cantidad_stock": "5",
                "stock_minimo": "1",
                "nueva_categoria": "Deportes",
            },
        )
        self.assertEqual(response.status_code, 302)
        producto = Producto.objects.get(nombre="Balón de fútbol")
        self.assertEqual(producto.categoria.nombre, "Deportes")
        self.assertEqual(producto.estado, Producto.PENDIENTE)
        self.assertTrue(Categoria.objects.filter(nombre="Deportes").exists())

    def test_producto_requiere_categoria_o_nueva_categoria(self):
        from .forms import ProductoForm

        form = ProductoForm(data={
            "nombre": "Sin categoría",
            "descripcion": "d",
            "categoria": "",
            "precio_venta": "10.00",
            "cantidad_stock": "1",
            "stock_minimo": "1",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("categoria", form.errors)

    def test_default_deportes_creado_por_ensure(self):
        from inventario.models import ensure_default_categorias

        ensure_default_categorias()
        self.assertTrue(Categoria.objects.filter(nombre="Deportes").exists())


class TokenEmpresaTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="TokenCorp",
            descripcion="Empresa del token",
            telefono="777",
            direccion="Av Token",
        )
        self.usuario = User.objects.create_user(
            username="token_boss",
            password="testpass",
            role="EMPRESA",
            email="boss@token.com",
        )
        self.usuario.empresa = self.empresa
        self.usuario.save()

    def test_generar_crea_token_unico_con_componente_correcta(self):
        instancia, creado = TokenEmpresa.generar(self.usuario, descripcion="App móvil")
        self.assertTrue(creado)
        self.assertTrue(instancia.token.startswith("tok_"))
        self.assertEqual(len(instancia.token), 52)
        self.assertEqual(instancia.usuario, self.usuario)
        self.assertEqual(instancia.descripcion, "App móvil")
        self.assertEqual(TokenEmpresa.objects.filter(usuario=self.usuario).count(), 1)

    def test_regenerar_actualiza_sin_duplicar(self):
        instancia1, _ = TokenEmpresa.generar(self.usuario, descripcion="Primera")
        token_antes = instancia1.token
        instancia2, creado = TokenEmpresa.generar(self.usuario, descripcion="Segunda")
        self.assertFalse(creado)
        self.assertEqual(instancia1.pk, instancia2.pk)
        self.assertNotEqual(token_antes, instancia2.token)
        self.assertEqual(instancia2.descripcion, "Segunda")
        self.assertEqual(TokenEmpresa.objects.filter(usuario=self.usuario).count(), 1)

    def test_filtro_por_token_devuelve_instancia(self):
        instancia, _ = TokenEmpresa.generar(self.usuario, descripcion="Búsqueda")
        encontrada = TokenEmpresa.por_token(instancia.token)
        self.assertEqual(encontrada, instancia)
        self.assertIsNone(TokenEmpresa.por_token("tok_inexistente"))

    def test_solo_empresa_accede_a_gestion(self):
        self.client.login(username="token_boss", password="testpass")
        from unittest import mock

        from django.test import client as django_test_client

        # Django 5.0 + Python 3.14: el test client copia el Context con
        # copy(context) y el __copy__ interno de Django revienta
        # ('super' object has no attribute 'dicts'). Parcheamos el receiver
        # solo para este render; no toca producción ni el framework.
        with mock.patch.object(
            django_test_client,
            "store_rendered_templates",
            new=lambda *args, **kwargs: None,
        ):
            response = self.client.get(reverse("token_empresa_gestion"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Token de acceso")

        empleado = User.objects.create_user(
            username="token_empleado", password="testpass", role="EMPLEADO"
        )
        self.client.login(username="token_empleado", password="testpass")
        response = self.client.get(reverse("token_empresa_gestion"))
        self.assertNotEqual(response.status_code, 200)

    def test_api_rechaza_sin_token(self):
        response = self.client.get(reverse("api_datos_empresa"))
        self.assertEqual(response.status_code, 401)

    def test_api_responde_datos_empresa_con_token_valido(self):
        instancia, _ = TokenEmpresa.generar(self.usuario, descripcion="API")
        Pedido.objects.create(
            cliente=self.usuario,
            empresa=self.empresa,
            estado=Pedido.PENDIENTE,
        )
        response = self.client.get(
            reverse("api_datos_empresa"),
            HTTP_AUTHORIZATION=f"Token {instancia.token}",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["empresa"]["nombre"], "TokenCorp")
        self.assertEqual(payload["kpis"]["pendientes"], 1)
