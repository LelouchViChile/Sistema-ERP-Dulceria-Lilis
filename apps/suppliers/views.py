from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def gestion_proveedores_view(request):
	"""
	Vista principal de gestión de proveedores.
	Por ahora usa datos de ejemplo para poblar la tabla.
	"""
	proveedores_demo = [
		{"rut": "76.123.456-7", "razon_social": "Dulces San Pedro Ltda.", "estado": "Activo", "email": "contacto@sanpedro.cl"},
		{"rut": "77.987.654-3", "razon_social": "ChocoMundo SPA", "estado": "Bloqueado", "email": "ventas@chocomundo.com"},
		{"rut": "75.555.555-5", "razon_social": "Gomitas S.A.", "estado": "Activo", "email": "soporte@gomitas.sa"},
	]

	context = {"proveedores": proveedores_demo}
	return render(request, "gestion_proveedores.html", context)
