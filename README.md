# Vigila tu Canasta

## URL pública

http://54.157.184.71:8501

## Vista General

**Vigila tu Canasta** es una aplicación creada para monitorear la evolución de los precios promedio de bienes y servicios en la Ciudad de México utilizando información pública del INEGI (**https://www.inegi.org.mx/app/preciospromedio/?bs=18a**)

El proyecto implementa la arquitectura **Medallion (Bronze / Silver / Gold)** sobre Amazon S3, permitiendo separar el almacenamiento de datos crudos, datos transformados y métricas analíticas listas para consumo.

Además del pipeline de datos, el proyecto incluye una aplicación interactiva desarrollada con **Streamlit**, donde los usuarios pueden:

- Construir canastas personalizadas de productos
- Monitorear la evolución histórica de precios
- Analizar inflación mensual y anual
- Optimizar canastas con base en inflación
- Guardar y recuperar canastas personalizadas

La solución fue desplegada utilizando:

- Amazon S3
- Amazon ECR
- Amazon ECS Fargate
- Docker
- Streamlit

El objetivo  de **Vigila tu casa** es poder ser una herramienta sencilla que permita al usuario poder llevar un registro más adecuado de los gastos, del presupuesto, de las dinámicas de precios de los alimentos, productos y servicios que consume con regularidad. 

## Arquitectura del Proyecto

### Bronze

Almacena los archivos originales descargados desde INEGI sin modificaciones.

---

### Silver

Transformaciones principales:
- Limpieza de registros
- Normalización de columnas
- Conversión de fechas
- Generación de `producto_id`
- Estandarización de unidades y cantidades
- Conversión a formato Parquet

Columnas principales:
- `anio`
- `mes`
- `fecha`
- `subclase`
- `generico`
- `especificacion`
- `precio_promedio`
- `cantidad`
- `unidad`
- `producto_id`

---

### Gold

Cálculos implementados:
- Precio anterior
- Inflación mensual
- Precio 12 meses
- Inflación anual
- Filtrado de productos activos (se eliminaron aquellos que dejaron de aparecer en la base después de 12 meses)

Métricas principales:
- `inflacion_mensual`
- `inflacion_anual`

---

### Infraestructura en la nube

El proyecto fue desplegado sobre AWS utilizando:

- **Amazon S3** → almacenamiento de datos y persistencia
- **Amazon ECR** → almacenamiento de imágenes Docker
- **Amazon ECS Fargate** → ejecución serverless de la aplicación
- **Docker** → empaquetado reproducible de la aplicación
- **IAM** → control de permisos y acceso a recursos AWS

## Estructura del Repositorio

```bash
.
├── app
├── config
├── data
│   └── raw
├── infra
│   └── s3.py
├── notebooks
│   ├── docker_build.ipynb
│   └── eda.ipynb
├── src
│   ├── bronze
│   │   ├── bronze.py
│   ├── gold
│   │   ├── gold.py
│   └── silver
│       └── silver.py
├── .dockerignore
├── .gitignore
├── Dockerfile
├── README.md
└── requirements.txt
```
---

### `app/`

Aplicación desarrollada con Streamlit.

Archivo principal:
- `app.py` → interfaz principal de la aplicación

---

### `config/`

Configuraciones auxiliares utilizadas por el proyecto.

---

### `data/`

Datos originales descargados desde INEGI.

---

### `infra/`

Recursos relacionados con infraestructura y deployment (S3)

---

### `notebooks/`

Notebooks utilizados para:
- exploración de datos
- validación del pipeline
- deployment en AWS

Notebook principal de deployment:
- `docker_build.ipynb`

---

### `src/`

Lógica principal del pipeline de datos.

Incluye:
- procesamiento Bronze → Silver
- procesamiento Silver → Gold
- cálculos de inflación
- transformaciones y limpieza

---

### `Dockerfile`

Define la imagen Docker utilizada para ejecutar la aplicación en ECS Fargate.

---

### `requirements.txt`

Lista de librerías necesarias para ejecutar la aplicación y el pipeline.

## Funcionalidades principales

La aplicación contiene cuatro secciones principales:

1. **Construir canasta**

Permite seleccionar productos:
- producto genérico
- especificación
- cantidad
- unidad

---

2. **Ver evolución**

Permite visualizar la evolución histórica de la canasta seleccionada.

Incluye:
- evolución agregada de la canasta

---

3. **Optimizar canasta**

Permite identificar alternativas dentro de la información disponible con menor inflación mensual.

---

4. **Canastas guardadas**

Permite guardar y cargar canastas personalizadas.

---

### Persistencia

La aplicación no depende únicamente del estado local de Streamlit.

Las canastas creadas por el usuario se guardan en Amazon S3, permitiendo:
- persistencia entre sesiones
- recuperación posterior de configuraciones
- separación entre aplicación y almacenamiento
- ejecución cloud sin depender de archivos locales

## Deployment en AWS

### Amazon ECR

La imagen Docker es almacenada en Amazon Elastic Container Registry (ECR).

---

### Amazon ECS Fargate

La aplicación fue desplegada utilizando Amazon ECS Fargate, corre como una tarea ECS dentro de un servicio Fargate configurado sobre una VPC de AWS.

---

### Seguridad y permisos

El proyecto utiliza IAM Roles para permitir acceso controlado a:
- Amazon S3
- Amazon ECR
- ECS Tasks

Esto permite que la aplicación:
- lea datasets desde S3
- guarde canastas personalizadas
- acceda a imágenes Docker almacenadas en ECR

---

### Deployment reproducible

El flujo completo de deployment fue documentado en notebooks del proyecto e incluye:

1. Construcción de imagen Docker
2. Login a Amazon ECR
3. Push de imagen a ECR
4. Creación de ECS Cluster
5. Registro de Task Definition
6. Configuración de networking
7. Deployment en ECS Fargate
8. Exposición pública de la aplicación

Notebook principal:

notebooks/docker_build.ipynb
