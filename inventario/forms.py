from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import (
    Categoria,
    CustomUser,
    Empresa,
    Movimiento,
    Producto,
    Proveedor,
    Resena,
    SolicitudEmpleado,
    Sugerencia,
)


class RegistroUsuarioForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        label="Tipo de usuario",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))
    nombre_empresa = forms.CharField(
        max_length=150,
        required=False,
        label="Nombre de la empresa",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    descripcion_empresa = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        label="Descripción de la empresa",
    )
    telefono_empresa = forms.CharField(
        max_length=20,
        required=False,
        label="Teléfono de la empresa",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    direccion_empresa = forms.CharField(
        max_length=255,
        required=False,
        label="Dirección de la empresa",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    instagram_empresa = forms.CharField(
        max_length=255,
        required=False,
        label="Instagram de la empresa",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    pagina_web_empresa = forms.URLField(
        required=False,
        label="Página web de la empresa",
        widget=forms.URLInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = CustomUser
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "nombre_empresa",
            "descripcion_empresa",
            "telefono_empresa",
            "direccion_empresa",
            "instagram_empresa",
            "pagina_web_empresa",
            "password1",
            "password2",
        )
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "password1": forms.PasswordInput(attrs={"class": "form-control"}),
            "password2": forms.PasswordInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        if role == "EMPRESA" and not cleaned_data.get("nombre_empresa"):
            self.add_error("nombre_empresa", "Las empresas deben indicar un nombre.")
        return cleaned_data

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username and CustomUser.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso. Elige otro.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data["role"]
        if user.role == "EMPRESA":
            empresa = Empresa.objects.create(
                nombre=self.cleaned_data["nombre_empresa"],
                descripcion=self.cleaned_data.get("descripcion_empresa", ""),
                telefono=self.cleaned_data.get("telefono_empresa", ""),
                direccion=self.cleaned_data.get("direccion_empresa", ""),
                instagram=self.cleaned_data.get("instagram_empresa", ""),
                pagina_web=self.cleaned_data.get("pagina_web_empresa", ""),
                email=user.email or "",
            )
            user.empresa = empresa
        if commit:
            user.save()
        return user


class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = (
            "nombre",
            "descripcion",
            "telefono",
            "email",
            "direccion",
            "instagram",
            "pagina_web",
        )
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "instagram": forms.TextInput(attrs={"class": "form-control"}),
            "pagina_web": forms.URLInput(attrs={"class": "form-control"}),
        }


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = (
            "nombre",
            "descripcion",
            "imagen",
            "codigo_sku",
            "categoria",
            "proveedor",
            "precio_compra",
            "precio_venta",
            "cantidad_stock",
            "stock_minimo",
        )
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "imagen": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "codigo_sku": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "proveedor": forms.Select(attrs={"class": "form-select"}),
            "precio_compra": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "precio_venta": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "cantidad_stock": forms.NumberInput(attrs={"class": "form-control"}),
            "stock_minimo": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        precio_compra = cleaned_data.get("precio_compra")
        precio_venta = cleaned_data.get("precio_venta")
        if precio_compra is not None and precio_venta is not None and precio_venta < precio_compra:
            self.add_error("precio_venta", "El precio de venta no puede ser menor al costo de compra.")
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "email", "profile_image")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "profile_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class MovimientoForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = ("producto", "tipo_movimiento", "cantidad", "nota")
        widgets = {
            "producto": forms.Select(attrs={"class": "form-select"}),
            "tipo_movimiento": forms.Select(attrs={"class": "form-select"}),
            "cantidad": forms.NumberInput(attrs={"class": "form-control"}),
            "nota": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get("producto")
        tipo = cleaned_data.get("tipo_movimiento")
        cantidad = cleaned_data.get("cantidad")

        if producto and tipo and cantidad:
            if tipo == Movimiento.TIPO_SALIDA and producto.cantidad_stock < cantidad:
                self.add_error("cantidad", "No hay suficiente stock para registrar esta salida.")
        return cleaned_data


class SolicitudEmpleadoForm(forms.ModelForm):
    class Meta:
        model = SolicitudEmpleado
        fields = ("empresa",)
        widgets = {"empresa": forms.Select(attrs={"class": "form-select"})}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["empresa"].queryset = user.empresa.__class__.objects.all() if user.empresa else user.empresa.__class__.objects.none()


class SugerenciaForm(forms.ModelForm):
    class Meta:
        model = Sugerencia
        fields = ("titulo", "contenido")
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "contenido": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class ResenaForm(forms.ModelForm):
    class Meta:
        model = Resena
        fields = ("nombre_anonimo", "calificacion", "contenido")
        widgets = {
            "nombre_anonimo": forms.TextInput(attrs={"class": "form-control"}),
            "calificacion": forms.Select(attrs={"class": "form-select"}),
            "contenido": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        autor = self.initial.get("autor")
        nombre_anonimo = cleaned_data.get("nombre_anonimo")
        contenido = cleaned_data.get("contenido")
        calificacion = cleaned_data.get("calificacion")
        if not autor and not nombre_anonimo:
            self.add_error("nombre_anonimo", "Este comentario debe indicar un nombre si el usuario no está autenticado.")
        if calificacion is None:
            self.add_error("calificacion", "Debes indicar una calificación.")
        if not contenido or not contenido.strip():
            self.add_error("contenido", "El comentario no puede estar vacío.")
        return cleaned_data


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ("nombre", "descripcion")
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ("nombre_negocio", "telefono", "email", "direccion")
        widgets = {
            "nombre_negocio": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
        }
