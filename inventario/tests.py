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
from .models import Categoria, Empresa, Producto, Proveedor, Resena, SolicitudEmpleado, Movimiento

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
