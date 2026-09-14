from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils import timezone

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
    username = forms.CharField(
        required=False,
        label="Nombre de usuario",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    nombre_empresa = forms.CharField(
        max_length=150,
        required=False,
        label="Nombre de la empresa",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    rif_empresa = forms.CharField(
        max_length=50,
        required=False,
        label="RIF",
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
    cedula = forms.CharField(
        max_length=20,
        required=False,
        label="Cédula de identidad",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    telefono = forms.CharField(
        max_length=20,
        required=False,
        label="Teléfono",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    residencia = forms.CharField(
        max_length=255,
        required=False,
        label="Residencia",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    fecha_nacimiento = forms.DateField(
        required=False,
        label="Fecha de nacimiento",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    profile_image = forms.ImageField(
        required=False,
        label="Foto del empleado",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = CustomUser
        fields = (
            "role",
            "username",
            "email",
            "first_name",
            "last_name",
            "nombre_empresa",
            "rif_empresa",
            "descripcion_empresa",
            "telefono_empresa",
            "direccion_empresa",
            "password1",
            "password2",
            "cedula",
            "telefono",
            "residencia",
            "fecha_nacimiento",
            "profile_image",
        )
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "password1": forms.PasswordInput(attrs={"class": "form-control"}),
            "password2": forms.PasswordInput(attrs={"class": "form-control"}),
            "cedula": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "residencia": forms.TextInput(attrs={"class": "form-control"}),
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "profile_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        if role == "EMPRESA" and not cleaned_data.get("nombre_empresa"):
            self.add_error("nombre_empresa", "Las empresas deben indicar un nombre.")
        if role == "EMPRESA" and not cleaned_data.get("rif_empresa"):
            self.add_error("rif_empresa", "Las empresas deben indicar un RIF.")
        if role == "EMPLEADO":
            for campo in ("cedula", "telefono", "residencia"):
                if not cleaned_data.get(campo):
                    self.add_error(campo, "Este campo es obligatorio para empleados.")
        if role == "EMPRESA" and not cleaned_data.get("username"):
            nombre_base = (cleaned_data.get("nombre_empresa") or "empresa").strip().lower()
            username_base = "".join(ch for ch in nombre_base if ch.isalnum() or ch in "_") or "empresa"
            username_base = username_base[:20]
            base = username_base
            contador = 1
            while CustomUser.objects.filter(username__iexact=base).exists():
                base = f"{username_base}{contador}"
                contador += 1
            cleaned_data["username"] = base
        cedula = cleaned_data.get("cedula")
        if cedula:
            cedula = cedula.strip()
            cleaned_data["cedula"] = cedula
            if CustomUser.objects.filter(cedula__iexact=cedula).exists():
                self.add_error("cedula", "Ya existe un usuario registrado con esta cédula.")
            elif role == "EMPLEADO" and not cleaned_data.get("username"):
                username_base = "".join(ch for ch in cedula if ch.isalnum() or ch in "_") or "empleado"
                username_base = username_base[:20]
                base = username_base
                contador = 1
                while CustomUser.objects.filter(username__iexact=base).exists():
                    base = f"{username_base}{contador}"
                    contador += 1
                cleaned_data["username"] = base
        fecha_nacimiento = cleaned_data.get("fecha_nacimiento")
        if fecha_nacimiento:
            fecha_min, fecha_max = limites_fecha_nacimiento()
            if fecha_nacimiento < fecha_min:
                self.add_error("fecha_nacimiento", "La fecha no es válida: la edad máxima permitida es 105 años.")
            elif fecha_nacimiento > fecha_max:
                self.add_error("fecha_nacimiento", "Debes ser mayor de edad (18 años) para registrarte.")
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        enable_spellcheck(self)
        orden_campos = [
            "role",
            "first_name",
            "last_name",
            "username",
            "email",
            "nombre_empresa",
            "rif_empresa",
            "descripcion_empresa",
            "telefono_empresa",
            "direccion_empresa",
            "cedula",
            "telefono",
            "residencia",
            "fecha_nacimiento",
            "profile_image",
            "password1",
            "password2",
        ]
        self.fields = {k: self.fields[k] for k in orden_campos if k in self.fields}
        fecha_min, fecha_max = limites_fecha_nacimiento()
        self.fields["fecha_nacimiento"].widget.attrs.update(
            {"min": fecha_min.isoformat(), "max": fecha_max.isoformat()}
        )
        self.fields["username"].required = False
        if self.instance and self.instance.role == "EMPRESA":
            self.fields["username"].required = False

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if not username:
            return username
        if CustomUser.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso. Elige otro.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data["role"]
        user.username = self.cleaned_data.get("username") or user.username or "empresa"
        user.cedula = self.cleaned_data.get("cedula") or None
        user.telefono = self.cleaned_data.get("telefono", "")
        user.fecha_nacimiento = self.cleaned_data.get("fecha_nacimiento")
        if user.role == "EMPLEADO":
            user.residencia = self.cleaned_data.get("residencia", "")
            user.profile_image = self.cleaned_data.get("profile_image")
        if user.role == "EMPRESA":
            nombre_empresa = self.cleaned_data.get("nombre_empresa", "")
            user.username = user.username or (nombre_empresa.strip().lower().replace(" ", "_")[:20] or "empresa")
            empresa = Empresa.objects.create(
                nombre=nombre_empresa,
                descripcion=self.cleaned_data.get("descripcion_empresa", ""),
                telefono=self.cleaned_data.get("telefono_empresa", ""),
                rif=self.cleaned_data.get("rif_empresa", ""),
                direccion=self.cleaned_data.get("direccion_empresa", ""),
                email=user.email or "",
            )
            user.empresa = empresa
        if commit:
            user.save()
        return user


def enable_spellcheck(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.Textarea) or getattr(widget, "input_type", "") == "text":
            widget.attrs.setdefault("spellcheck", "true")


def limites_fecha_nacimiento():
    hoy = timezone.localdate()

    def restar_anios(anios):
        try:
            return hoy.replace(year=hoy.year - anios)
        except ValueError:
            return hoy.replace(year=hoy.year - anios, day=28)

    return restar_anios(105), restar_anios(18)


class SpellcheckModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        enable_spellcheck(self)


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Nombre de usuario",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
                "autocapitalize": "none",
                "readonly": "readonly",
                "onfocus": "this.removeAttribute('readonly')",
            }
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
                "readonly": "readonly",
                "onfocus": "this.removeAttribute('readonly')",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        enable_spellcheck(self)


class EmpresaForm(SpellcheckModelForm):
    class Meta:
        model = Empresa
        fields = (
            "nombre",
            "descripcion",
            "telefono",
            "email",
            "rif",
            "direccion",
            "instagram",
            "pagina_web",
        )
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "rif": forms.TextInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "instagram": forms.TextInput(attrs={"class": "form-control"}),
            "pagina_web": forms.URLInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["instagram"].label = "Redes sociales"


class ProductoForm(SpellcheckModelForm):
    class Meta:
        model = Producto
        fields = (
            "nombre",
            "descripcion",
            "imagen",
            "categoria",
            "precio_venta",
            "cantidad_stock",
            "stock_minimo",
        )
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "imagen": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "precio_venta": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "cantidad_stock": forms.NumberInput(attrs={"class": "form-control"}),
            "stock_minimo": forms.NumberInput(attrs={"class": "form-control"}),
        }
        help_texts = {
            "nombre": "Nombre visible para los clientes en el catálogo.",
            "descripcion": "Describe el producto con detalles útiles para la venta.",
            "imagen": "La imagen se mostrará en el catálogo.",
            "categoria": "Selecciona la categoría a la que pertenece el producto.",
            "precio_venta": "Precio final que verá el cliente.",
            "cantidad_stock": "Cantidad disponible actualmente en inventario.",
            "stock_minimo": "Monto mínimo sugerido antes de reponer stock.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("codigo_sku", None)
        self.fields.pop("proveedor", None)
        self.fields.pop("precio_compra", None)

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.codigo_sku:
            import uuid
            instance.codigo_sku = f"AUTO-{uuid.uuid4().hex[:8].upper()}"
        if not instance.proveedor_id:
            default_proveedor, _ = Proveedor.objects.get_or_create(
                nombre_negocio="Proveedor general",
                defaults={
                    "telefono": "000000000",
                    "email": "",
                    "direccion": "General",
                },
            )
            instance.proveedor = default_proveedor
        if instance.precio_compra is None:
            instance.precio_compra = instance.precio_venta
        if commit:
            instance.save()
        return instance


class UserProfileForm(SpellcheckModelForm):
    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "email", "profile_image", "fecha_nacimiento")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "profile_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.role == "EMPRESA":
            self.fields.pop("fecha_nacimiento")
            return
        fecha_min, fecha_max = limites_fecha_nacimiento()
        self.fields["fecha_nacimiento"].widget.attrs.update(
            {"min": fecha_min.isoformat(), "max": fecha_max.isoformat()}
        )

    def clean(self):
        cleaned_data = super().clean()
        fecha_nacimiento = cleaned_data.get("fecha_nacimiento")
        if fecha_nacimiento:
            fecha_min, fecha_max = limites_fecha_nacimiento()
            if fecha_nacimiento < fecha_min:
                self.add_error("fecha_nacimiento", "La fecha no es válida: la edad máxima permitida es 105 años.")
            elif fecha_nacimiento > fecha_max:
                self.add_error("fecha_nacimiento", "Debes ser mayor de edad (18 años) para registrarte.")
        return cleaned_data


class MovimientoForm(SpellcheckModelForm):
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


class SolicitudEmpleadoForm(SpellcheckModelForm):
    class Meta:
        model = SolicitudEmpleado
        fields = ("empresa",)
        widgets = {"empresa": forms.Select(attrs={"class": "form-select"})}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["empresa"].queryset = user.empresa.__class__.objects.all() if user.empresa else user.empresa.__class__.objects.none()


class SugerenciaForm(SpellcheckModelForm):
    class Meta:
        model = Sugerencia
        fields = ("titulo", "contenido")
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "contenido": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class ResenaForm(SpellcheckModelForm):
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


class CategoriaForm(SpellcheckModelForm):
    class Meta:
        model = Categoria
        fields = ("nombre", "descripcion")
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class ProveedorForm(SpellcheckModelForm):
    class Meta:
        model = Proveedor
        fields = ("nombre_negocio", "telefono", "email", "direccion")
        widgets = {
            "nombre_negocio": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
        }
