# EmploLeaks

EmploLeaks es una herramienta de OSINT (Open Source Intelligence) con una interfaz CLI , diseñada para descubrir y correlacionar información sobre empleados de una empresa objetivo. Permite recopilar perfiles de LinkedIn, generar emails corporativos potenciales, buscar credenciales filtradas en bases de datos de leaks (ClickHouse internamente), verificar brechas conocidas a través de HaveIBeenPwned, descubrir infraestructura de la empresa y perfilar empleados en redes sociales. Toda la información se almacena localmente en SQLite para su análisis posterior.

## Características

- Búsqueda y enumeración de empleados desde LinkedIn (scraping con cookies de sesión)
- Generación automática de emails corporativos potenciales con formatos personalizables
- Búsqueda de credenciales filtradas en base de datos ClickHouse propia
- Verificación de brechas conocidas con la API de HaveIBeenPwned
- Escaneo de secretos en repositorios GitHub/GitLab con gitleaks
- **Discovery de infraestructura:** enumeración de subdominios con assetfinder + SecurityTrails
- **Profiling en redes sociales:** búsqueda por email (Holehe, ~120 plataformas) y por username (Maigret, 500+ plataformas)
- **Telegram scraper (userbot):** daemon standalone que se une a canales aprobados de Telegram y baja archivos de credenciales automáticamente
- **Parser de leaks 100% agéntico:** sin regex hardcodeadas. Un agente IA propone schema, valida con score sobre la muestra, recibe feedback con ejemplos de errores, y reintenta hasta converger. Auto-detecta UTF-16/UTF-8, banners ASCII art, country code prefixes, stealer logs (Redline/Lumma/Raccoon), formatos email/user/url arbitrarios
- Almacenamiento local de toda la información en SQLite
- Generación de reportes HTML interactivos con fotos de perfil
- Clasificación automática de empleados por departamento usando IA (OpenAI, Ollama, etc.)
- Exportación de resultados a CSV
- Sistema modular de plugins (LinkedIn, GitHub, HIBP)
- Autoguardado y carga automática de configuración de plugins
- Webapp administrativa con FastAPI + Next.js para triage de resultados

## Estructura del Proyecto

```
emploleaks/
├── emploleaks.py             # Script principal (CLI interactiva con cmd2)
├── telegram_sync.py          # Daemon userbot de Telegram (Telethon, standalone)
├── requirements.txt          # Dependencias de Python
├── README.md
├── .gitignore
├── plugins/
│   ├── linkedin.py           # Plugin de LinkedIn (scraping de empleados)
│   ├── github.py             # Plugin de GitHub (repos, stalk, secrets)
│   └── hibp.py               # Plugin de HaveIBeenPwned (brechas)
├── utils/
│   ├── logging_format.py     # Configuración de logging con colores
│   ├── ai_classifier.py      # Clasificación de roles con IA (OpenAI/Ollama)
│   ├── leak_parser.py        # Parser de leaks 100% agéntico (loop de IA, sin regex)
│   ├── email_lookup.py       # Búsqueda de emails en redes sociales (Holehe)
│   ├── profile_lookup.py     # Búsqueda de usernames en redes sociales (Maigret)
│   └── discovery.py          # Enumeración de subdominios (assetfinder + SecurityTrails opcional)
├── clickhouse-docker/        # Docker Compose para levantar ClickHouse
│   ├── docker-compose.yml
│   └── config/
│       └── users.xml
├── leaks_data/               # Carpeta para archivos de leaks a importar (no en git)
├── config/                   # Configuración (autogenerado)
│   └── tokens.ini            # Tokens y credenciales de plugins (no en git)
├── data/                     # Base de datos local (autogenerado)
│   └── emploleaks.db         # SQLite con toda la información recopilada
├── webapp/                   # Webapp administrativa
│   ├── backend/              # FastAPI (Python)
│   └── frontend/             # Next.js (React/TypeScript)
└── logs/                     # Archivos de log (autogenerado)
    └── log.txt
```

## Requisitos

- Python 3.10+
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
| `list_companies` | Muestra todas las empresas |
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
| `connect_leaks` | Conectar a ClickHouse usando la configuración guardada en `tokens.ini` |
| `connect_leaks --host <host> --port <port> --save` | Conectar con parámetros específicos y guardarlos para futuras sesiones |
| `disconnect_leaks` | Desconectar de la base de datos ClickHouse |
| `import_leaks [directorio]` | Importar archivos de credenciales a ClickHouse (default: `leaks_data/`) |
| `import_leaks --no-ai` | Importar solo archivos con formato conocido, sin usar IA |
| `create_db --user <user> --passwd <pass> --dbname <db> [--import-data <dir>]` | Crear la BD ClickHouse manualmente (legacy) |

La conexión a ClickHouse se configura en `config/tokens.ini`:
```ini
[clickhouse]
host = localhost
port = 9000
user = default
passwd =
dbname = credentials_db
```

Si ClickHouse está configurado en `tokens.ini`, la conexión se establece automáticamente al iniciar.

### Búsqueda de Credenciales y Brechas

| Comando | Descripción |
|---------|-------------|
| `find_passwords <modo>` | Busca credenciales en ClickHouse + [ProxyNova COMB](https://www.proxynova.com/tools/comb/) (3.2B credentials). Modos: `find_all`, `only_usernames`, `only_emails` |
| `find_passwords <modo> --no-proxynova` | Solo busca en ClickHouse local |
| `find_passwords <modo> --no-clickhouse` | Solo busca en ProxyNova COMB (no requiere ClickHouse) |
| `find_passwords <modo> --email <email>` | Busca credenciales para un email específico |
| `find_breaches` | Busca brechas en HIBP para todos los emails de la empresa (requiere plugin `hibp` activo) |

**ProxyNova COMB** es una base de datos pública con 3.2 mil millones de credenciales filtradas (Combination Of Many Breaches). No requiere API key y se consulta automáticamente en cada búsqueda. Usar `--no-proxynova` para desactivarla.

### Discovery de Infraestructura

| Comando | Descripción |
|---------|-------------|
| `add_domain <dominio>` | Asocia un dominio a la empresa seleccionada (ej: `add_domain faradaysec.com`) |
| `discover` | Ejecuta enumeración de subdominios contra todos los dominios de la empresa usando `assetfinder` (+ SecurityTrails opcional), resolviendo DNS |
| `print --data domains` | Muestra los dominios registrados y la cantidad de subdominios encontrados |
| `print --data subdomains` | Muestra todos los subdominios con su IP, fuente y fecha de descubrimiento |

El módulo de Discovery delega la enumeración pasiva a [`assetfinder`](https://github.com/tomnomnom/assetfinder), que internamente agrega resultados de crt.sh, HackerTarget, BufferOver y otras fuentes sin API key. Se espera el binario en `$PATH` (instalación: `go install github.com/tomnomnom/assetfinder@latest`).

Opcionalmente, si configurás una API key de SecurityTrails sus subdominios se mergean con los de assetfinder:
```ini
[discovery]
# securitytrails_key = your_key_here
```

### Profiling en Redes Sociales

| Comando | Descripción |
|---------|-------------|
| `lookup_emails` | Busca emails confirmados en ~120 plataformas con Holehe |
| `lookup_emails --include-potential` | Incluye también los emails generados |
| `lookup_emails --email user@mail.com` | Busca un email específico |
| `lookup_emails --all` | Busca en las 120+ plataformas (no solo las configuradas) |
| `lookup_emails --list-platforms` | Lista todas las plataformas disponibles |
| `lookup_profiles` | Busca perfiles por username con Maigret (requiere usernames cargados) |
| `lookup_profiles --employee "Juan"` | Busca solo para un empleado específico |

**Holehe** (email lookup): utiliza la técnica de "forgot password" para determinar si un email está registrado en cada plataforma, sin alertar al dueño. Las plataformas se configuran en `tokens.ini`:
```ini
[holehe]
platforms = google, discord, github, instagram, twitter, spotify, ...
```

**Maigret** (username lookup): busca si un username existe en 500+ plataformas de redes sociales. Los usernames se agregan manualmente por empleado desde la webapp. Las plataformas se filtran opcionalmente en `tokens.ini`:
```ini
[maigret]
# platforms = instagram, twitter, facebook, tiktok, reddit, github
```

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
| `print --data domains` | Muestra dominios registrados |
| `print --data subdomains` | Muestra subdominios descubiertos |
| `print --data all` | Muestra todo consolidado por empleado |
| `print --data all --html` | Genera un reporte HTML interactivo con fotos |
| `print --data all --html --ai` | Genera reporte HTML agrupando empleados por departamento usando IA |
| `print --data <tipo> --export` | Exporta los datos a un archivo CSV con timestamp |

### Configuración de IA y Clasificación

| Comando | Descripción |
|---------|-------------|
| `set_ai --endpoint <url> --key <key> --model <modelo>` | Configura el proveedor de IA |
| `classify` | Clasifica empleados en departamentos usando IA (se guarda en la BD) |
| `classify --force` | Re-clasifica aunque ya tengan departamento asignado |

La clasificación por IA analiza los títulos/roles de los empleados y los agrupa por departamento (Engineering, Security, Sales, etc.). Los departamentos se persisten en SQLite y son visibles en el reporte HTML y en la webapp.

**Proveedores soportados** (cualquier API compatible con OpenAI):
- **Ollama (local, por defecto):** `set_ai --endpoint http://localhost:11434/v1 --model llama3`
- **OpenAI:** `set_ai --endpoint https://api.openai.com/v1 --key sk-... --model gpt-4o-mini`
- **Cualquier otro compatible:** LM Studio, Together AI, etc.

### Telegram Scraper (Userbot)

Daemon standalone que usa una cuenta personal de Telegram (vía Telethon) para unirse a canales/grupos aprobados, descargar archivos `.txt/.csv/.dat/.zip/.gz` y dejarlos en `leaks_data/telegram/<chat>/`. El `import_leaks` posterior los ingiere a ClickHouse usando el parser agéntico. **Decoupled del CLI** — corre como proceso aparte, así puede estar 24/7 sin que la CLI esté abierta.

**Setup inicial (one-time):**

1. Crear app en https://my.telegram.org/apps para obtener `api_id` y `api_hash`.
2. Agregar al `config/tokens.ini`:
   ```ini
   [telegram]
   api_id = 12345678
   api_hash = abcd1234...
   session = config/telegram.session
   download_root = leaks_data/telegram
   allowed_extensions = txt, csv, dat, zip, gz
   default_backfill_limit = 10
   ```
3. Login interactivo (te pide tu número, código por app, opcionalmente 2FA):
   ```bash
   python3.13 telegram_sync.py login
   ```

**Subcomandos:**

| Comando | Descripción |
|---------|-------------|
| `login` | Autenticación inicial. Persiste sesión en `config/telegram.session` |
| `list_groups` | Lista todos los chats/canales donde está tu cuenta, y los snapshotea en SQLite |
| `approve <chat_id> [--limit N]` | Marca un chat como aprobado y corre backfill de los últimos N mensajes |
| `unapprove <chat_id>` | Quita la aprobación |
| `list_approved` | Tabla de chats aprobados con conteo de archivos bajados |
| `backfill <chat_id> [--limit N]` | Re-baja los últimos N mensajes de un chat aprobado |
| `run [--watch]` | Backfill de todos los aprobados; con `--watch` queda escuchando NewMessage events |
| `status` | Resumen: aprobados / archivos bajados / disco usado |

**Tablas nuevas en `data/emploleaks.db`:**

| Tabla | Descripción |
|-------|-------------|
| `telegram_groups` | Snapshot de chats (chat_id, title, username, approved, backfill_limit, last_sync_at) |
| `telegram_files` | Archivos bajados con dedup por `(chat_id, message_id)` y por `SHA-256` del contenido |

**Daemon en background:**
```bash
nohup python3.13 telegram_sync.py run --watch >> logs/telegram.log 2>&1 &
echo $! > /tmp/telegram_daemon.pid
# Para parar:
# kill $(cat /tmp/telegram_daemon.pid)
```

---

### Parser de Leaks 100% Agéntico

El módulo `utils/leak_parser.py` usa **únicamente un agente de IA** para parsear cada archivo. No hay regex hardcodeadas (fueron eliminadas porque cada formato nuevo introducía bugs sutiles de extracción).

**Pipeline del agente:**
```
1. Auto-detectar encoding (BOM sniffing): utf-8 / utf-8-sig / utf-16 / utf-32.
2. Sampling inteligente: tomar las primeras 80 líneas que parezcan credenciales
   (con separadores típicos, alfanumérico >50%) — skipea banners ASCII art.
3. La IA recibe 50 líneas + system prompt con familias comunes de formato y
   propone {separator, fields, skip_lines}.
4. Aplicamos el schema a la muestra SIN filtros → list of tuples.
5. Validamos con _is_clean_credential → score = % rows válidas.
6. Si score ≥ 0.8 y ≥ 5 rows → aplicar al archivo completo.
7. Si no → mandar al agente la (source_line ↔ extracción mala) en pares,
   más checklist de errores típicos. Goto 3.
8. Hasta 7 iteraciones. Si no converge a 0.8: fallback al mejor schema si
   alcanzó ≥ 0.7. Bajo eso → skip con warning (nunca ingerimos basura).
```

**`_is_clean_credential` — validación transversal:**
- Username: longitud 1-64, sin `/ : \ space`, no empieza con `http/android/ftp//`.
- Password: longitud 1-256, sin `/`, máximo un `:`, sin whitespace, no empieza con URL prefix.

**Determinismo:** `temperature=0` en todas las llamadas + en-memory caching dentro de un mismo run. El mismo archivo produce el mismo schema entre runs → `import_leaks` es idempotente.

**Costo típico:** 1-3 llamadas al API por archivo, ~$0.0001-$0.0005 con gpt-4o-mini. Para 12 archivos: ~$0.005 = medio centavo.

---

### Webapp Administrativa

| Comando | Descripción |
|---------|-------------|
| `python emploleaks.py --webapp` | Lanza la webapp (backend en :8421, frontend en :3421) |

La webapp permite:
- Dashboard con estadísticas, hallazgos clave y acciones rápidas
- Gestión de empleados con secciones colapsables por departamento y drag & drop
- **Connected Accounts**: visualizar perfiles en redes sociales, buscar por email (Holehe) y por username (Maigret)
- **Discovery**: gestionar dominios, ejecutar enumeración de subdominios, ver resultados con IP y fuente
- Triage de credenciales y secretos (marcar como verificado, no funciona, falso positivo)
- Edición de emails y usernames por empleado (agregar, modificar, eliminar)
- Clasificación con IA desde la interfaz

---

## Plugins

### LinkedIn

Permite buscar empleados de una empresa en LinkedIn usando cookies de sesión del navegador, y generar emails corporativos potenciales. Captura automáticamente el logo de la empresa.

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

La carpeta `leaks_data/` se monta como volumen de solo lectura dentro del contenedor.

### Importar credenciales

1. Colocá tus archivos de leaks (`.txt`, `.csv`, `.dat`, `.zip`, `.gz`) en la carpeta `leaks_data/`.
2. Ejecutá el comando de importación:

```
emploleaks> import_leaks
```

El parser detecta automáticamente los formatos más comunes:
- `email:password`
- `email:password:url`
- `email;password`
- `email|password`
- `url,email,password`

Para formatos desconocidos, utiliza la IA configurada (OpenAI/Ollama) para analizar una muestra del archivo y determinar cómo parsearlo. Usá `--no-ai` para omitir la detección con IA.

Archivos `.zip` y `.gz` se descomprimen automáticamente antes de parsear.

### Buscar credenciales

```
emploleaks(miempresa)> find_passwords only_emails
emploleaks(miempresa)> find_passwords find_all
emploleaks(miempresa)> print --data passwords
```

Si ClickHouse está configurado en `tokens.ini`, la conexión es automática al iniciar la herramienta.

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
| `companies` | Empresas registradas (nombre, logo) |
| `employees` | Empleados descubiertos (nombre, título, foto, empresa, departamento) |
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
| `social_profiles` | Perfiles en redes sociales (Holehe + Maigret) |
| `domains` | Dominios de la empresa para discovery |
| `subdomains` | Subdominios descubiertos (IP, fuente, fecha) |
| `usernames` | Usernames asociados a empleados para Maigret |

---

## Flujo de Trabajo Típico

```
1. python emploleaks.py

# Gestión de empresa
2. add_company --name target_corp
3. select_company --name target_corp

# Scraping de LinkedIn (captura empleados + logo de empresa)
4. use --plugin linkedin
5. setopt JSESSIONID <cookie>
6. setopt li-at <cookie>
7. run impersonate
8. run find target_corp targetcorp.com --email-format {n}.{s}
9. print --data emails

# Discovery de infraestructura
10. add_domain targetcorp.com
11. discover
12. print --data subdomains

# Credenciales filtradas (ClickHouse se conecta automáticamente desde config)
13. find_passwords only_emails

# Brechas conocidas
14. use --plugin hibp
15. setopt apikey <hibp_key>
16. find_breaches

# Secretos en repositorios
17. use --plugin github
18. setopt token <github_token>
19. run find_secrets

# Profiling en redes sociales (por email)
20. deactivate
21. lookup_emails

# Profiling en redes sociales (por username, requiere cargar usernames en webapp)
22. lookup_profiles

# Clasificación por departamento
23. classify

# Reportes y exportación
24. print --data all --export
25. print --data all --html --ai

# Webapp para triage interactivo
26. python emploleaks.py --webapp

# Telegram scraper (proceso aparte, en otra terminal)
27. python3.13 telegram_sync.py login           # one-time
28. python3.13 telegram_sync.py list_groups
29. python3.13 telegram_sync.py approve <chat_id> --limit 5
30. python3.13 telegram_sync.py run --watch     # daemon en watch
# Archivos van a leaks_data/telegram/... → re-ejecutar import_leaks los absorbe.
```

## Disclaimer

Esta herramienta está diseñada únicamente para fines educativos, de investigación en seguridad y pruebas de pentesting autorizadas. El uso de esta herramienta para actividades maliciosas o no autorizadas está estrictamente prohibido. Los usuarios son responsables de cumplir con todas las leyes y términos de servicio del proyecto.
