# Django ERP (Django + Unfold)

Sistema ERP modular desarrollado en Django con interfaz de administración moderna basada en **Unfold**. 
Diseñado inicialmente para la gestión de Almancén, inventario, compras, ventas y facturacion, con arquitectura preparada para adaptarse a cualquier negocio estandar.


## 🚀 Tecnologías Utilizadas
- **Backend:** Python 3.10+, Django 4.2+
- **Frontend:** Unfold (Dashboard moderno)
- **Base de Datos:** PostgreSQL / SQLite (Desarrollo)
- **Estilos:** Tailwind CSS (Gestionado internamente por Unfold)


## Filosofia

- Solucionar problemas es mas importante que el desarrollo perfecto de ultima tecnologia.
- Menos es mas - Interfaces simples para la comodidad de el usuario.
- Mecanicas de desarrollo rapido, django + Unfold crean los CRUD por ti y la IA agiliza procesos.
- Crear modulos lo mas independiente posible y que sea reutilizable.


## Intrucciones para correr el proyecto:


- python -m venv venv

- source venv/bin/activate  # Linux/Mac

- # O en Windows: venv\Scripts\activate

- git clone https://github.com/victormagallanes2/django_erp.git

- cd django_erp

- pip install -r requirements.txt

- python manage.py makemigrations

- python manage.py migrate

- python manage.py collectstatic

- python manage.py runserver


## Carga de datos inicial


Datos obligatorios para que el proyecto funcione adecuadamente esto incluye, monedas, metodos de pago, grupos y permisos. Situarse donde esta el archivo manage.py y ejecutar:

  - python -m django_erp.configuration.data.load_data


1. Una vez dentro en configuracion - Tasa de cambio, establecer la tasa de cambio al dia segun el bcv.

2. Crear Empresa en el menu configuracion - Empresa y fijar la tasa de iva que pagara en el campo iva.


## Funcionamiento o flujo basico):

1. Crear un Almacen o almacenes que se usara en Almacen - Ubicaciones.

2. Crear productos en Almacen - Productos.

3. Para añadir productos al inventarios se debe crear ordenes de compras.

4. Para restar al inventarios se debe crear ordenes de ventas.


## Mecanica de desarrollo


- Por simplicidad se desarrolla en sqlite3 (Tener cuidado con compatibilidad con postgres).
- Se crean los modelos y se usa el admin para las interfaces y el CRUD, usar librerias que trae unfold por defecto en su core ejemplo widget, inlineform, Graficos Chart.js etc.. este es el link de la documentacion: https://unfoldadmin.com/docs/installation/quickstart/
- Si vas a usar IA como apoyo se recomienda pasar todo el proyecto en un txt para ello se usa gitingest, esto es para que la ia tenga contexto, ademas se recomienda solo crear partes estrictamente supervisada y tener cuidado de no romper lo existente y por ultimo no hacer chat extensos ya que llega un momento en que la IA tiene alucinaciones, entonces es mejor iniciar un chat nuevo y volver a pasar el proyecto actualizado con los ultimos cambios aprobados.
- Los menus se crean en el settings.py en el diccionario UNFOLD



## Otros comandos

- Eliminar migraciones:

Get-ChildItem -Path . -Recurse -Include "*.py" -Exclude "__init__.py" | Where-Object { $_.Directory.Name -eq "migrations" } | Remove-Item -Force






