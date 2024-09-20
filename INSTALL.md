# Utopia CRM installation guide

## Install requirements

- Python:

  The Python version we recomend to use is any version from 3.10.6 to 3.11.6

  If your system has a native Python installation in version 3.10.6 - 3.11.6 you can use it, and no installing another Python version may be required.

  If not, we recommend installing version 3.11.6 using [pyenv](https://github.com/pyenv/pyenv)

- System packages:

  NOTES: package names can vary by OS/distribution.

  - `postgresql` (Version 11+ is required)
  - `postgis`

## Local installation for development in Linux or Mac (Devs / DevOps)

### Clone the source code

Open a terminal and go to the directory where you want to save the project source code, then clone the repository from GitHub with:

`git clone -b main https://github.com/ladiaria/utopia-crm.git`

and change to that folder

`cd utopia-crm`

### Create a virtual environment and install CRM dependencies

Create a virtualenv (venv) for Python3 (the subdirectory `~/.virtualenvs` is not needed, we use it in this guide because is the default virtualenv directory in the tool [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/), also the virtual environment name can be any other, "utopiacrm" is chosen in this guide):

  NOTE: if using pyenv, this venv creation is done a bit different, consult the pyenv documentation for that.

  `user@host:~/utopia-crm $ mkdir -p ~/.virtualenvs && virtualenv ~/.virtualenvs/utopiacrm`

- Activate the new virtual environment and install the required Python modules:

  ```bash
  user@host:~/utopia-crm $ source ~/.virtualenvs/utopiacrm/bin/activate
  (utopiacrm) user@host:~/utopia-crm $ pip install --upgrade pip && pip install -r requirements.txt
  ```

### Database setup

Create a database user and the database, this can be done in many different ways, the simplest way, when you have access to the database superuser (`postgres`) "via sudo" is the one we choose for this guide:

Note: the default password we use in the sample settings file in the next step is "utopiadev_django", the same as the username.

```bash
# Execute these commands, entering a new password for the new user beeing create, this password will be used in next
# step, don't forget it.
sudo -u postgres createuser -DPS utopiadev_django
sudo -u postgres createdb -O utopiadev_django utopiadev
sudo -u postgres psql -c "CREATE EXTENSION postgis;" utopiadev
```

### Local configuration

Copy `local_settings_sample.py` to `local_settings.py` and configure the database in the new file by modifiying the `DATABASE` variable with the values created in the previous step. And also fill the `SECRET_KEY` variable using any string or a more secure one generated for example with [this web tool](https://djecrety.ir/).

### Extra configuration for macOS

In the case that you're using macOS, it is necessary that you specify where "gdal" and "geos" are located. You'll have to install them through brew and then locate where the files are stored to add the following settings. Please note that these settings are for the last version of ARM MacOS computers. Your homebrew folder can differ for intel based MacOS computers. These settings will be commented in local_settings_sample.py.

```python
GDAL_LIBRARY_PATH = "/opt/homebrew/opt/gdal/lib/libgdal.dylib"
GEOS_LIBRARY_PATH = "/opt/homebrew/opt/geos/lib/libgeos_c.dylib"
```

To install these packages refer to the following websites.
[geos homebrew](https://formulae.brew.sh/formula/geos)
[gdal homebrew](https://formulae.brew.sh/formula/gdal)

### Create the database structure

Run "migrate":

`(utopiacrm) user@host:~/utopia-crm$ python manage.py migrate`

An output like this will appear:

```console
Operations to perform:
  Apply all migrations: admin, admin_honeypot, auth, authtoken, community, contenttypes, core, invoicing, logistics, sessions, support, taggit
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  Applying admin.0001_initial... OK
  Applying admin.0002_logentry_remove_auto_add... OK
  Applying admin_honeypot.0001_initial... OK
...
```

### Create a Django superuser to login into the CRM's web interface

Run the following command:

```bash
(utopiacrm) user@host:~/utopia-crm$ python manage.py createsuperuser
```

And follow the prompts to create your super user.

WARNING: This user has ALL permissions on the application database. It is recommended that you only give superuser permissions to people you trust. It can be deleted if it's not necessary.

### Create the default groups and populate them with their permissions

Run the following command, which will create the default groups for the application with some basic permissions.

```bash
(utopiacrm) user@host:~/utopia-crm$ python manage.py loaddata fixtures/default_groups.json
```

### Running the application

Start the development server by running:

```bash
(utopiacrm) user@host:~/utopia-crm$ python manage.py runserver
```

and go to the following URL in your browser: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

### Known issues for MacOS

It is possible that you encounter this error when running the server for the first time:

`ModuleNotFoundError: No module named 'dns'`

To solve this issue, navigate to where your virtualenv is located and find the site-packages folder under the folder lib/pythonX.XX/ where X.XX is your python version. There you might find an uppercase DNS folder that you can safely rename to lowercase "dns". In the case your error shows that the module not found is an uppercase DNS, you can do the opposite.

### Optional: Enabling Mercado Pago Integration

To enable Mercado Pago integration:

1. Install additional requirements:

   ```bash
   pip install -r mercadopago_requirements.txt
   ```

2. Copy `local_mercadopago_settings_sample.py` to `local_mercadopago_settings.py`

3. Edit `mercadopago_settings.py`:
   - Set `MERCADOPAGO_ENABLED = True`
   - Add your Mercado Pago access token: `MERCADOPAGO_ACCESS_TOKEN = "your_access_token_here"`

4. Run migrations:

   ```bash
   python manage.py migrate
   ```
