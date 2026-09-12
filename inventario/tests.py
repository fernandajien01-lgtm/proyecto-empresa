from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import EmpresaForm, RegistroUsuarioForm, ResenaForm
from .models import Categoria, Empresa, Producto, Proveedor, SolicitudEmpleado, Movimiento

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


class ProductoListAccessTests(TestCase):
    def test_guest_comment_redirects_to_register(self):
        response = self.client.post(
            reverse("producto_list"),
            {"producto_id": 999, "contenido": "Comentario de invitado", "calificacion": 5},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("register"))


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
