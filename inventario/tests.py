from django.test import TestCase
from django.urls import reverse

from .forms import EmpresaForm, RegistroUsuarioForm, ResenaForm


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
            "username": "empresa1",
            "email": "empresa1@example.com",
            "first_name": "",
            "last_name": "",
            "role": "EMPRESA",
            "nombre_empresa": "Mi tienda",
            "descripcion_empresa": "Venta de productos",
            "telefono_empresa": "5551234",
            "direccion_empresa": "Calle 123",
            "instagram_empresa": "@mitienda",
            "pagina_web_empresa": "https://mitienda.com",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        self.assertTrue(form.is_valid(), form.errors)


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
