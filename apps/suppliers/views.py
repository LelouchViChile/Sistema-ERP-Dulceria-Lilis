from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from datetime import datetime

# Intentar cargar openpyxl para exportar a Excel
try:
	from openpyxl import Workbook
	from openpyxl.utils import get_column_letter
except ImportError:
	Workbook = None


@login_required
def gestion_proveedores_view(request):
	"""
	Vista principal de gestión de proveedores.
	Por ahora usa datos de ejemplo para poblar la tabla,
	con búsqueda, paginación y exportación a Excel.
	"""
	proveedores_demo = [
		{"rut": "76.123.456-7", "razon_social": "Dulces San Pedro Ltda.", "estado": "Activo", "email": "contacto@sanpedro.cl"},
		{"rut": "77.987.654-3", "razon_social": "ChocoMundo SPA", "estado": "Bloqueado", "email": "ventas@chocomundo.com"},
		{"rut": "75.555.555-5", "razon_social": "Gomitas S.A.", "estado": "Activo", "email": "soporte@gomitas.sa"},
		{"rut": "78.111.222-4", "razon_social": "CandyCorp Ltda.", "estado": "Inactivo", "email": "info@candycorp.com"},
		{"rut": "79.999.333-1", "razon_social": "Azúcar & Miel SPA", "estado": "Activo", "email": "ventas@azucarymiel.cl"},
	]

	# --- Filtros GET ---
	query = request.GET.get('q', '').strip()
	sort_by = request.GET.get('sort', 'razon_social')
	export = request.GET.get('export')

	# --- Filtrado por búsqueda ---
	if query:
		proveedores_demo = [
			p for p in proveedores_demo
			if query.lower() in p['razon_social'].lower()
			or query.lower() in p['rut'].lower()
			or query.lower() in p['email'].lower()
			or query.lower() in p['estado'].lower()
		]

	# --- Ordenamiento simple ---
	reverse = sort_by.startswith('-')
	key = sort_by.lstrip('-')
	proveedores_demo.sort(key=lambda x: x.get(key, ''), reverse=reverse)

	# --- Exportar a Excel ---
	if export == 'xlsx':
		if Workbook is None:
			return HttpResponse(
				"Falta dependencia: instala openpyxl (pip install openpyxl)",
				status=500,
				content_type="text/plain; charset=utf-8"
			)

		wb = Workbook()
		ws = wb.active
		ws.title = "Proveedores"
		headers = ["RUT", "Razón Social", "Estado", "Email"]
		ws.append(headers)

		for p in proveedores_demo:
			ws.append([p["rut"], p["razon_social"], p["estado"], p["email"]])

		# Ajuste de columnas
		for col in ws.columns:
			max_len = 0
			col_letter = get_column_letter(col[0].column)
			for cell in col:
				max_len = max(max_len, len(str(cell.value)) if cell.value else 0)
			ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

		response = HttpResponse(
			content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
		)
		filename = f"proveedores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
		response["Content-Disposition"] = f'attachment; filename="{filename}"'
		wb.save(response)
		return response

	# --- Paginación ---
	paginator = Paginator(proveedores_demo, 10)
	page_number = request.GET.get('page')
	page_obj = paginator.get_page(page_number)

	context = {
		'page_obj': page_obj,
		'query': query,
		'sort_by': sort_by
	}
	return render(request, "gestion_proveedores.html", context)
