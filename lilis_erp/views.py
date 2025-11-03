from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required(login_url='login')
def dashboard_page(request):
    """
    Vista para renderizar la página principal (dashboard.html).
    Solo accesible para usuarios autenticados.
    """
    return render(request, 'dashboard.html')
