from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.producto_list, name="producto_list"),
    path("registro/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", views.custom_logout, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("chat/", views.chat_list, name="chat_list"),
    path("chat/<int:user_id>/", views.chat_con_usuario, name="chat_con_usuario"),
    path("empresa/editar/", views.empresa_editar, name="empresa_editar"),
    path("solicitudes/", views.solicitudes_empresa, name="solicitudes_empresa"),
    path("solicitud/<int:pk>/confirmar-aceptar/", views.confirmar_aceptar_solicitud, name="confirmar_aceptar_solicitud"),
    path("solicitud/<int:pk>/<str:estado>/", views.actualizar_solicitud, name="actualizar_solicitud"),
    path("empresa/<int:empresa_id>/", views.empresa_detalle, name="empresa_detalle"),
    path("empresa/<int:empresa_id>/solicitar/", views.solicitar_union_empresa, name="solicitar_union_empresa"),
    path("empresa/<int:empresa_id>/cancelar/", views.cancelar_solicitud, name="cancelar_solicitud"),
    path("mis-solicitudes/", views.mis_solicitudes, name="mis_solicitudes"),
    path("sugerencia/", views.sugerencia_crear, name="sugerencia_crear"),
    path("categoria/nueva/", views.categoria_crear, name="categoria_crear"),
    path("proveedor/nuevo/", views.proveedor_crear, name="proveedor_crear"),
    path("producto/nuevo/", views.producto_crear, name="producto_crear"),
    path("producto/<int:pk>/editar/", views.producto_editar, name="producto_editar"),
    path("producto/<int:pk>/eliminar/", views.producto_eliminar, name="producto_eliminar"),
    path("producto/<int:pk>/pedido/", views.realizar_pedido, name="realizar_pedido"),
    path("dejar_empresa/", views.dejar_empresa, name="dejar_empresa"),
    path("quitar_empleado/<int:empleado_id>/", views.quitar_empleado, name="quitar_empleado"),
    path("editar_perfil/", views.editar_perfil, name="editar_perfil"),
    path("confirmar_eliminar_cuenta/", views.confirmar_eliminar_cuenta, name="confirmar_eliminar_cuenta"),
    path("movimiento/nuevo/", views.movimiento_crear, name="movimiento_crear"),
    path("producto/<int:producto_id>/resena/", views.resena_crear, name="resena_crear"),
    path("producto/<int:producto_id>/reaccion/<str:tipo>/", views.reaccion_producto, name="reaccion_producto"),
    path("resena/<int:resena_id>/reaccion/<str:tipo>/", views.reaccion_resena, name="reaccion_resena"),
    path("resena/<int:pk>/editar/", views.resena_editar, name="resena_editar"),
]
