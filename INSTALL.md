# Utopia CRM installation guide

## Requirements

- **Python**: 3.10.6 – 3.12.8 (constrained by Django 4.2). If your system Python is outside this range, use [pyenv](https://github.com/pyenv/pyenv) to install a supported version.
- **System packages** (names may vary by OS/distribution):
  - `postgresql` (version 11+)
  - `postgis`
  - `gdal` / `libgdal-dev`
  - `geos` / `libgeos-dev`

---

## Local installation for development (Linux or macOS)

### 1. Clone the repository

```bash
git clone -b main https://github.com/ladiaria/utopia-crm.git
cd utopia-crm
```

### 2. Create a virtual environment and install dependencies

```bash
mkdir -p ~/.virtualenvs && virtualenv ~/.virtualenvs/utopiacrm
source ~/.virtualenvs/utopiacrm/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
```

> If you are using pyenv, virtual environment creation works differently — consult the pyenv documentation.

### 3. Database setup

The simplest approach when you have `sudo` access to the `postgres` superuser:

```bash
sudo -u postgres createuser -DPS utopiadev_django
sudo -u postgres createdb -O utopiadev_django utopiadev
sudo -u postgres psql -c "CREATE EXTENSION postgis;" utopiadev
sudo -u postgres psql -c "CREATE EXTENSION unaccent;" utopiadev
```

The default password used in the sample settings file is `utopiadev_django`.

### 4. Local configuration

Copy the sample settings file and edit it:

```bash
cp local_settings_sample.py local_settings.py
```

- Set `SECRET_KEY` to any non-empty string (or generate one with [djecrety.ir](https://djecrety.ir/)).
- Verify the `DATABASES` block matches the user and database name you created above.

#### Extra step for macOS

On macOS, GDAL and GEOS are installed by Homebrew to non-standard paths. Install them first:

```bash
brew install gdal geos
```

Then add the following to your `local_settings.py` (adjust paths if on Intel Mac):

```python
GDAL_LIBRARY_PATH = "/opt/homebrew/opt/gdal/lib/libgdal.dylib"
GEOS_LIBRARY_PATH = "/opt/homebrew/opt/geos/lib/libgeos_c.dylib"
```

If the server fails to start with a GDAL-related error even after setting these paths, see [GDAL troubleshooting](#gdal-troubleshooting-macos) below.

### 5. Create the database structure

```bash
python manage.py migrate
```

### 6. Load default groups and permissions

This creates the default user groups for the base application:

```bash
python manage.py loaddata default_groups
```

> If you are installing with a customization package (see [Extending utopia-crm](#extending-utopia-crm) below), skip this step and run the richer fixture from your package instead — it includes the base groups plus any extension-specific permissions.

### 7. Populate required lookup data

```bash
python manage.py populate_seller_console_actions
```

### 8. Create a superuser

```bash
python manage.py createsuperuser
```

Follow the prompts. This user has all permissions — only grant it to people you trust.

### 9. Start the development server

```bash
python manage.py runserver 0:8001
```

Go to [http://127.0.0.1:8001/](http://127.0.0.1:8001/) in your browser.

---

## Known issues

### GDAL troubleshooting (macOS)

Django's GeoDjango bindings need to load `libgdal` as a shared library. If the Homebrew GDAL version doesn't match what Django expects, you may see errors like:

```
OSError: cannot load library 'gdal': ...
django.core.exceptions.ImproperlyConfigured: Could not find the GDAL library
```

**Option 1: verify the Homebrew path**

The path varies between Apple Silicon and Intel Macs, and between GDAL versions. Check what you actually have:

```bash
find /opt/homebrew -name "libgdal*.dylib" 2>/dev/null   # Apple Silicon
find /usr/local -name "libgdal*.dylib" 2>/dev/null       # Intel
```

Use the exact path you find in `local_settings.py`.

**Option 2: use the GDAL bundled with Postgres.app**

If you use [Postgres.app](https://postgresapp.com/), it ships its own GDAL build that is already version-matched to PostGIS. This is often the most reliable option on macOS:

```python
GDAL_LIBRARY_PATH = "/Applications/Postgres.app/Contents/Versions/latest/lib/libgdal.dylib"
GEOS_LIBRARY_PATH = "/opt/homebrew/opt/geos/lib/libgeos_c.dylib"
```

Note: GEOS still comes from Homebrew in this setup — only GDAL is taken from Postgres.app. If GEOS also fails, check its path the same way:

```bash
find /opt/homebrew -name "libgeos_c*.dylib" 2>/dev/null
```


### macOS: `ModuleNotFoundError: No module named 'dns'`

`py3dns` was removed from `requirements.txt` — DNS support now comes from `dnspython` (pulled in automatically by `pyIsEmail`), which always installs as `dns/` (lowercase) and doesn't have this problem.

If you see this error anyway — e.g. because you installed `py3dns` manually or have an old virtualenv — it's a case-sensitivity mismatch. When pip installs py3DNS, the folder in `site-packages` may be `DNS/` (uppercase) or `dns/` (lowercase) depending on the version. On macOS the filesystem is case-insensitive so it installs without complaint, but Python's import system can still fail depending on which case it expects.

Fix: find the folder and rename it to match what the error expects:

```bash
ls ~/.virtualenvs/utopiacrm/lib/pythonX.XX/site-packages/ | grep -i dns
mv ~/.virtualenvs/utopiacrm/lib/pythonX.XX/site-packages/DNS \
   ~/.virtualenvs/utopiacrm/lib/pythonX.XX/site-packages/dns
```

---

## Optional configuration

### Mercado Pago integration

Add the following to `local_settings.py`:

```python
MERCADOPAGO_ENABLED = True
MERCADOPAGO_PUBLIC_KEY = "your_public_key"
MERCADOPAGO_ACCESS_TOKEN = "your_access_token"
```

Mercado Pago requires HTTPS for callbacks and redirects — make sure your server has it enabled.

### Separate cache for django-select2

By default, django-select2 uses Django's default cache. For better performance with large contact datasets, configure a dedicated cache backend in `local_settings.py`.

With Redis:

```bash
pip install django-redis
```

```python
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "select2": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    },
}
SELECT2_CACHE_BACKEND = "select2"
```

With Memcached:

```python
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "select2": {
        "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
        "LOCATION": "127.0.0.1:11211",
    },
}
SELECT2_CACHE_BACKEND = "select2"
```

---

## Extending utopia-crm

utopia-crm is designed to be extended without modifying the base source code. If you are building or installing a customization package (like `utopia-crm-ladiaria`), follow these additional steps after completing the base installation above.

### Install your package in development mode

From your package's root directory:

```bash
pip install -e /path/to/your-customization-package
```

This makes the package importable and lets you edit its source without reinstalling.

### Register the package in `local_settings.py`

Add your app to `INSTALLED_APPS` and point the URL router at your custom URL module:

```python
INSTALLED_APPS += ["your_package_name"]
URLS_CUSTOM_MODULE = "your_package_name.urls"
```

This causes `urls.py` to prepend your URL patterns before the base ones, allowing overrides.

### Run your package's migrations

```bash
python manage.py migrate
```

### Load your package's groups fixture

Replace the base `default_groups` loaddata step with your package's full groups fixture, which includes both the base permissions and any extension-specific ones:

```bash
python manage.py loaddata your_groups_fixture_name
```

### Load any additional bootstrap fixtures your package requires

Consult your package's `COMMANDS.md` or `INSTALL.md` for the full list of fixtures and management commands that need to run on a fresh database.
