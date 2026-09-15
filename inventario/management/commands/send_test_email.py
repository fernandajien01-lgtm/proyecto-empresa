from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envía un correo de prueba para verificar la configuración SMTP."

    def add_arguments(self, parser):
        parser.add_argument("destinatario", nargs="?", help="Dirección de correo que recibirá la prueba.")

    def handle(self, *args, **options):
        destino = options["destinatario"] or input("Correo que recibirá la prueba: ").strip()
        if not destino:
            raise CommandError("Debes indicar un correo destinatario.")

        if not settings.EMAIL_HOST_USER:
            raise CommandError(
                "No hay credenciales configuradas (EMAIL_HOST_USER vacío en .env). "
                "Completa .env antes de probar."
            )

        try:
            sent = send_mail(
                "Fer&Jos Inventory - Correo de prueba",
                (
                    "¡Hola!\n\nEste es un correo de prueba para confirmar que el envío funciona. "
                    "Si lo recibes, el sistema de recuperación de contraseña también debería funcionar.\n\n"
                    "Fer&Jos Inventory"
                ),
                settings.DEFAULT_FROM_EMAIL,
                [destino],
                fail_silently=False,
            )
        except Exception as exc:
            raise CommandError("Error al enviar: %s" % exc)

        self.stdout.write(
            self.style.SUCCESS(
                "Correo de prueba enviado a %s (backend: %s). Revisa tu bandeja (y spam)."
                % (destino, settings.EMAIL_BACKEND.rsplit(".")[-1])
            )
        )