# Comandos técnicos reproducibles

## Intérprete recomendado

ANNA — Interactive Video Activities for AAC debe ejecutarse y verificarse con Python 3.12 mediante el lanzador de Windows:

```powershell
py -3.12 hotspot_editor.py
```

## Pruebas

```powershell
py -3.12 -m pytest
```

## Dependencias

Dependencias de ejecución:

```powershell
py -3.12 -m pip install -r requirements.txt
```

Dependencias de desarrollo y pruebas:

```powershell
py -3.12 -m pip install -r requirements-dev.txt
```

## Nota de entorno

Si `py -3.12` no aparece en `py -0p`, instala o registra Python 3.12 antes de ejecutar ANNA o la suite Qt. No uses el Python 3.9 de Visual Studio como entorno de referencia para este proyecto.
