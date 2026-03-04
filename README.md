![Python](https://img.shields.io/badge/Python-3.x-blue)
![Django](https://img.shields.io/badge/Django-6.x-success)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![License](https://img.shields.io/badge/License-Acad%C3%A9mico-lightgrey)

# Sistema de Gestión de Inventario y Pedidos

Prototipo web desarrollado como trabajo de titulación para la carrera de **Ingeniería en Sistemas de Información** en la **Pontificia Universidad Católica del Ecuador (PUCE)**.

El sistema permite gestionar **inventario y pedidos dentro de un entorno de comercio electrónico**, facilitando el control de productos, stock y gestión de pedidos.

---

# Descripción del sistema

Este proyecto consiste en el desarrollo de un **prototipo web de gestión de inventario y pedidos**, diseñado para apoyar la administración de productos dentro de una empresa que opera en un entorno de comercio electrónico.

El sistema permite:

* Registrar productos en inventario
* Gestionar el stock disponible
* Administrar pedidos
* Visualizar información de productos
* Facilitar el control de inventario dentro de la organización

Este prototipo fue desarrollado utilizando el framework **Django**, siguiendo una arquitectura basada en el patrón **Modelo-Vista-Template (MVT)**.

---

# Tecnologías utilizadas

* Python
* Django
* PostgreSQL
* HTML
* CSS
* JavaScript

---

# Instalación

## 1. Clonar el repositorio

```
git clone https://github.com/SalvadorOrt/sistema-inventario-ecommerce.git
```

Entrar a la carpeta del proyecto:

```
cd sistema-inventario-ecommerce
```

---

## 2. Crear entorno virtual

```
python -m venv venv
```

Activar el entorno virtual.

En Windows:

```
venv\Scripts\activate
```

En Linux / Mac:

```
source venv/bin/activate
```

---

## 3. Instalar dependencias

```
pip install -r requirements.txt
```

---

# Configuración de base de datos

El sistema utiliza **PostgreSQL** como gestor de base de datos.

Crear una base de datos en PostgreSQL:

```
CREATE DATABASE inventario_db;
```

Luego configurar la conexión en el archivo:

```
proyecto/settings.py
```

Ejemplo de configuración:

```
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'inventario_db',
        'USER': 'postgres',
        'PASSWORD': 'tu_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

---

# Aplicar migraciones

Ejecutar el siguiente comando para crear las tablas en la base de datos:

```
python manage.py migrate
```

---

# Ejecutar el servidor

```
python manage.py runserver
```

Luego abrir en el navegador:

```
http://127.0.0.1:8000/
```

---

# Estructura del proyecto

```
sistema-inventario-ecommerce
│
├── media
├── miapp
├── tienda
├── proyecto
├── manage.py
├── requirements.txt
└── README.md
```

---

# Autor

**Salvador Andrés Ortega Martínez**

Ingeniería en Sistemas de Información
Pontificia Universidad Católica del Ecuador (PUCE)

---

