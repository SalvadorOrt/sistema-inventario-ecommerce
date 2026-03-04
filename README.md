![Python](https://img.shields.io/badge/Python-3.x-blue)
![Django](https://img.shields.io/badge/Django-6.x-success)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![License](https://img.shields.io/badge/License-Acad%C3%A9mico-lightgrey)
## Arquitectura (alto nivel)

```mermaid
flowchart LR
  U[Usuario] --> W[Interfaz Web (Templates)]
  W --> DJ[Django (Views/URLs)]
  DJ --> M[Models/ORM]
  M --> DB[(PostgreSQL)]
  DJ --> ST[Static Files]
  DJ --> MD[Media Files]
# Sistema de Gestión de Inventario y Pedidos

Prototipo web desarrollado como trabajo de titulación para la carrera de Ingeniería en Sistemas de Información.

El sistema permite gestionar inventario y pedidos dentro de un entorno de comercio electrónico.

## Tecnologías utilizadas

- Python
- Django
- PostgreSQL
- HTML
- CSS
- JavaScript

## Instalación

1. Clonar el repositorio

git clone https://github.com/SalvadorOrt/sistema-inventario-ecommerce.git

2. Instalar dependencias

pip install -r requirements.txt

3. Ejecutar migraciones

python manage.py migrate

4. Ejecutar servidor

python manage.py runserver

## Autor

Salvador Andrés Ortega Martínez  
Pontificia Universidad Católica del Ecuador
