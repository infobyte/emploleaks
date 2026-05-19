# EmploLeaks

EmploLeaks es una herramienta de OSINT (Open Source Intelligence) con interfaz CLI interactiva, diseñada para descubrir y correlacionar información sobre empleados de una empresa objetivo. Permite recopilar perfiles de LinkedIn, generar emails corporativos potenciales, buscar credenciales filtradas en bases de datos de leaks (ClickHouse) y verificar brechas conocidas a través de HaveIBeenPwned. Toda la información se almacena localmente en SQLite para su análisis posterior.

## Características

- Búsqueda y enumeración de empleados desde LinkedIn (scraping con cookies de sesión)
- Generación automática de emails corporativos potenciales con formatos personalizables
- Búsqueda de credenciales filtradas en base de datos ClickHouse propia
- Verificación de brechas conocidas con la API de HaveIBeenPwned
- Escaneo de secretos en repositorios GitHub/GitLab con gitleaks
- Almacenamiento local de toda la información en SQLite
- Exportación de resultados a CSV
- Sistema modular de plugins (LinkedIn, GitHub, HIBP)
- Autoguardado y carga automática de configuración de plugins

## Estructura del Proyecto

```
emploleaks/
├── emploleaks.py             # Script principal (CLI interactiva con cmd2)
├── requirements.txt          # Dependencias de Python
├── README.md
├── .gitignore
├── plugins/
│   ├── linkedin.py           # Plugin de LinkedIn (scraping de empleados)
│   ├── github.py             # Plugin de GitHub (repos, stalk, secrets)
│   └── hibp.py               # Plugin de HaveIBeenPwned (brechas)
├── utils/
│   └── logging_format.py     # Configuración de logging con colores
├── workflows/                # Scripts de automatización (legacy)
│   ├── check_leaked_passwords.py
│   └── get_public_repos.py
├── clickhouse-docker/        # Docker Compose para levantar ClickHouse
│   ├── docker-compose.yml
│   └── config/
│       └── users.xml
├── config/                   # Configuración (autogenerado)
│   └── tokens.ini            # Tokens y credenciales de plugins (no en git)
├── data/                     # Base de datos local (autogenerado)
│   └── emploleaks.db         # SQLite con toda la información recopilada
└── logs/                     # Archivos de log (autogenerado)
    └── log.txt
```

## Requisitos

- Python 3.8+
- pip
- Conexión a Internet
- **Opcional:** Docker y Docker Compose (para levantar ClickHouse localmente)
- **Opcional:** [gitleaks](https://github.com/gitleaks/gitleaks) (para escaneo de secretos en repos)
- **Opcional:** API key de [HaveIBeenPwned](https://haveibeenpwned.com/API/Key)
- Cookies de sesión de LinkedIn (`JSESSIONID` y `li_at`) para el plugin de LinkedIn

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/yourusername/emploleaks.git
cd emploleaks
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. (Opcional) Levantar ClickHouse con Docker para la base de datos de leaks:
```bash
cd clickhouse-docker
docker compose up -d
cd ..
```

## Uso

Ejecutar la herramienta:
```bash
python emploleaks.py
```

Con modo debug:
```bash
python emploleaks.py -d
```

### Comandos Generales

| Comando | Descripción |
|---------|-------------|
| `help` | Muestra la ayuda general |
| `help <comando>` | Muestra la ayuda de un comando específico |
| `quit` | Sale de la aplicación |

### Gestión de Empresas

| Comando | Descripción |
|---------|-------------|
| `add_company --name <nombre>` | Agrega una nueva empresa |
| `select_company --name <nombre>` | Selecciona una empresa para trabajar |
| `list_companies list` | Muestra todas las empresas |
| `delete_company --name <nombre>` | Elimina una empresa y todos sus datos |

### Gestión de Plugins

| Comando | Descripción |
|---------|-------------|
| `use --plugin <nombre>` | Activa un plugin (`linkedin`, `github`, `hibp`) |
| `deactivate` | Desactiva el plugin actual |
| `show options` | Muestra las opciones del plugin activo |
| `setopt <opción> [valor]` | Configura una opción del plugin (si no se pasa valor, se pide por prompt oculto) |
| `autosave --enable / --disable` | Activa/desactiva el guardado automático de configuración en `config/tokens.ini` |
| `autoload --enable / --disable` | Activa/desactiva la carga automática de configuración desde `config/tokens.ini` |

### Conexión a Base de Datos de Leaks (ClickHouse)

| Comando | Descripción |
|---------|-------------|
| `connect_leaks --user <user> --passwd <pass> --dbname <db> [--host <host>] [--port <port>] [--secure]` | Conectar a la base de datos ClickHouse |
| `disconnect_leaks` | Desconectar de la base de datos ClickHouse |
| `create_db --user <user> --passwd <pass> --dbname <db> [--host <host>] [--port <port>] [--secure] [--import-data <directorio>]` | Crear la base de datos ClickHouse e importar datos de credenciales |

### Búsqueda de Credenciales y Brechas

| Comando | Descripción |
|---------|-------------|
| `find_passwords <modo>` | Busca credenciales filtradas en ClickHouse. Modos: `find_all`, `only_usernames`, `only_emails` |
| `find_passwords <modo> --email <email>` | Busca credenciales para un email específico |
| `find_breaches` | Busca brechas en HIBP para todos los emails de la empresa (requiere plugin `hibp` activo) |

### Visualización y Exportación

| Comando | Descripción |
|---------|-------------|
| `print --data emails` | Muestra emails confirmados y potenciales |
| `print --data passwords` | Muestra credenciales encontradas |
| `print --data breaches` | Muestra brechas de HIBP |
| `print --data gits` | Muestra cuentas de GitHub |
| `print --data twitters` | Muestra cuentas de Twitter/X |
| `print --data phones` | Muestra números de teléfono |
| `print --data websites` | Muestra sitios web |
| `print --data secrets` | Muestra secretos encontrados en repositorios |
| `print --data all` | Muestra todo consolidado por empleado |
| `print --data <tipo> --export` | Exporta los datos a un archivo CSV con timestamp |

---

## Plugins

### LinkedIn

Permite buscar empleados de una empresa en LinkedIn usando cookies de sesión del navegador, y generar emails corporativos potenciales.

**Opciones:**

| Opción | Descripción |
|--------|-------------|
| `JSESSIONID` | Cookie de sesión JSESSIONID de LinkedIn |
| `li-at` | Cookie de sesión li_at de LinkedIn |
| `hide` | Ocultar el valor de JSESSIONID al mostrarlo (default: `yes`) |

**Comandos disponibles dentro del plugin:**

| Comando | Descripción |
|---------|-------------|
| `run impersonate` | Autenticar usando las cookies configuradas |
| `run find <company_linkedin> <dominio_email> [--email-format FORMAT]` | Buscar empleados y generar emails |

**Formatos de email disponibles:**
- Por defecto: `f_last` (ej: `jsmith@domain.com`) y `f.last` (ej: `j.smith@domain.com`)
- Custom con `--email-format`: usa placeholders `{n}` (inicial nombre), `{s}` (apellido), `{name}` (nombre completo), `{l}` (inicial apellido)
  - Ejemplo: `--email-format {n}.{s}` genera `j.smith@domain.com`

**Ejemplo completo:**
```
emploleaks> add_company --name miempresa
emploleaks> select_company --name miempresa
emploleaks(miempresa)> use --plugin linkedin
emploleaks(miempresa)(linkedin)> setopt JSESSIONID
JSESSIONID: <se ingresa oculto>
emploleaks(miempresa)(linkedin)> setopt li-at
li-at: <se ingresa oculto>
emploleaks(miempresa)(linkedin)> run impersonate
emploleaks(miempresa)(linkedin)> run find miempresa miempresa.com --email-format {n}.{s}
```

### GitHub

Permite obtener información de perfiles GitHub, listar repositorios, y escanear secretos en repositorios con gitleaks.

**Opciones:**

| Opción | Descripción |
|--------|-------------|
| `token` | Token de acceso personal de GitHub |
| `blur` | Ofuscar el token al mostrarlo |
| `gitleaks_path` | Ruta al binario de gitleaks (default: `gitleaks` en PATH) |
| `max_repo_size` | Tamaño máximo de repo a analizar en MB (default: `15`) |

**Comandos disponibles dentro del plugin:**

| Comando | Descripción |
|---------|-------------|
| `run stalk <username>` | Obtener email de una cuenta GitHub |
| `run get_repos <username>` | Listar repositorios públicos de un usuario |
| `run find_secrets` | Escanear secretos en repos de empleados de la empresa |
| `run find_secrets --download-all` | Igual pero sin límite de tamaño |

**Ejemplo completo:**
```
emploleaks(miempresa)> use --plugin github
emploleaks(miempresa)(github)> setopt token ghp_xxxxxxxxxxxx
emploleaks(miempresa)(github)> run find_secrets
emploleaks(miempresa)(github)> print --data secrets
```

### HaveIBeenPwned (HIBP)

Verifica si los emails de la empresa aparecen en brechas conocidas usando la API de HIBP.

**Opciones:**

| Opción | Descripción |
|--------|-------------|
| `apikey` | API key de HaveIBeenPwned |
| `rate_limit` | Delay entre llamadas a la API en segundos (default: `2.0`) |

**Comandos disponibles dentro del plugin:**

| Comando | Descripción |
|---------|-------------|
| `run find_breaches` | Buscar brechas para todos los emails de la empresa |
| `find_breaches` | Comando directo (equivalente, requiere plugin hibp activo) |

**Ejemplo completo:**
```
emploleaks(miempresa)> use --plugin hibp
emploleaks(miempresa)(hibp)> setopt apikey <tu_api_key>
emploleaks(miempresa)(hibp)> find_breaches
emploleaks(miempresa)(hibp)> print --data breaches
```

---

## Base de Datos de Leaks (ClickHouse)

EmploLeaks puede conectarse a una base de datos ClickHouse propia con credenciales filtradas para buscar passwords asociados a los emails/usernames de los empleados descubiertos.

### Levantar ClickHouse con Docker

```bash
cd clickhouse-docker
docker compose up -d
```

Esto expone ClickHouse en:
- Puerto `9000` (protocolo nativo TCP)
- Puerto `8123` (interfaz HTTP)

### Crear la base de datos e importar datos

```
emploleaks> create_db --user default --passwd "" --dbname credentials_db --host localhost --port 9000 --import-data /ruta/a/archivos/
```

El formato esperado de los archivos de importación es: `email:password:url` (un registro por línea, archivos `.txt`, `.csv` o `.dat`).

### Conectarse y buscar credenciales

```
emploleaks> connect_leaks --user default --passwd "" --dbname credentials_db --host localhost --port 9000
emploleaks(miempresa)> find_passwords only_emails
emploleaks(miempresa)> find_passwords find_all
emploleaks(miempresa)> print --data passwords
```

### Estructura de la tabla `credentials` en ClickHouse

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `mail_username` | String | Parte del usuario del email |
| `mail_domain` | String | Dominio del email (sin TLD) |
| `mail_tld` | String | TLD del email |
| `password` | String | Contraseña filtrada |
| `uri_subdomain` | String | Subdominio del sitio donde se filtró |
| `uri_domain` | String | Dominio del sitio |
| `uri_tld` | String | TLD del sitio |

---

## Estructura de la Base de Datos Local (SQLite)

| Tabla | Descripción |
|-------|-------------|
| `companies` | Empresas registradas |
| `employees` | Empleados descubiertos (nombre, título, empresa) |
| `emails` | Emails confirmados (obtenidos de contact_info de LinkedIn) |
| `potential_emails` | Emails potenciales generados por formato |
| `passwords` | Contraseñas encontradas asociadas a emails |
| `username_passwords` | Contraseñas encontradas por username |
| `breaches` | Brechas de HIBP asociadas a emails |
| `githubs` | URLs de perfiles/repos GitHub |
| `twitters` | URLs de perfiles Twitter/X |
| `phones` | Números de teléfono |
| `websites` | Sitios web personales |
| `secrets_repos` | Secretos encontrados en repositorios con gitleaks |

---

## Flujo de Trabajo Típico

```
1. python emploleaks.py

2. add_company --name target_corp
3. select_company --name target_corp

4. use --plugin linkedin
5. setopt JSESSIONID <cookie>
6. setopt li-at <cookie>
7. run impersonate
8. run find target_corp targetcorp.com --email-format {n}.{s}

9. print --data emails

10. connect_leaks --user default --passwd "" --dbname credentials_db
11. find_passwords only_emails

12. use --plugin hibp
13. setopt apikey <hibp_key>
14. find_breaches

15. use --plugin github
16. setopt token <github_token>
17. run find_secrets

18. print --data all --export
```

## Disclaimer

Esta herramienta está diseñada únicamente para fines educativos, de investigación en seguridad y pruebas de penetración autorizadas. El uso de esta herramienta para actividades maliciosas o no autorizadas está estrictamente prohibido. Los usuarios son responsables de cumplir con todas las leyes y términos de servicio aplicables.

emploleaks(f)(linkedin)> setopt JSESSIONID ajax:2879580135233792831
[+] Updating value successfull
emploleaks(f)(linkedin)> setopt li-at AQEDAWXbSjMB0js_AAABnPxoCDEAAAGdIHSMMU0AFhUxs-qYd0Qia0eXL0pM8KOTciw7vPZSBus-yak5NiDqjXeUf6S5OG2WVVEJ79GtCdcDmbTa9HGYN2g87JzuXuEcm8m2ouhFqEDyeytpVpuP3Buq
