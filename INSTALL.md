# Utopia Customer Relationship Management Installation

Documentation about installing Utopia's CRM.

## Code repository

Obtain the code from GitHub with:

`git clone git@github.com:ladiaria/utopia-crm.git`

and change to that folder

`cd utopia-crm`

## Create a virtual environment and install CRM dependencies

virtualenv is a tool to create an isolated Python environment, refer to: https://virtualenv.pypa.io/en/latest/ for installation.

Check virtualenv version and path:

`virtualenv --version`

A path including "python3.7" should be printed, if not, is probably that you have Python 2 as your default Python version,
you should then use the command virtualenv3 if you have Python 3.7 (**required**) already installed.

Create the virtual environment:

`virtualenv virtualenv_name`

(Use `virtualenv3` command if Python2 is the default Python version)

This last command will create a folder virtualenv_name where all Django and Python dependencies should be installed.

Activate the virtual enviroment:

`source virtualenv_name/bin/activate`

And then install all needed dependencies from requirements.txt file using pip:

`(virtualenv_name) user@user-machine:~/projects/utopia-crm$ pip install -r requirements.txt`

This will install all required dependencies in the virtualenv_name enviroment.

## Install requirements

`pip install -r requirements.txt`

## Postgres database setup

In this example a PostgreSQL database is used, the following is a posible set up.

First create the database and role (Ubuntu):

```
sudo -i
su postgres
psql
```

You should be logged in as postgres with the command prompt:
`postgres=#`

And create a development database owned by utopiadev_owners:
Also, create the extension POSTGIS on this database. Make sure postgis is installed on your server.

```
CREATE DATABASE utopiadev;
\c utopiadev
CREATE ROLE utopiadev_owners;
ALTER DATABASE utopiadev OWNER TO utopiadev_owners;
ALTER SCHEMA public OWNER TO utopiadev_owners;
CREATE EXTENSION postgis;
```

Then create a user named utopiadev_django that Django will use in the migration to create CRM tables. The user should be created logged in as postgres user in your linux box:

`postgres@user-machine:/root$ createuser --interactive --pwprompt`

```
Enter name of role to add: utopiadev_django
Enter password for new role:
Enter it again:
Shall the new role be a superuser? (y/n) n
Shall the new role be allowed to create databases? (y/n) n
Shall the new role be allowed to create more new roles? (y/n) n
Password:
```

Finally, add this user to the role that has been created before.

Again:

```
sudo -i
su postgres
psql
```

Then on the postgres prompt, execute this command:

```
postgres=# GRANT utopiadev_owners TO utopiadev_django;
```

## Project configuration

In utopia-crm folder copy local_settings_sample.py to local_settings.py and configure the database by modifiying DATABASE variable. Write user and password for the utopiadev_django user recently created:
The following example assumes the utopiadev_django password is utopiadev_django:

```
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'utopiadev', 'USER': 'utopiadev_django', 'PASSWORD': 'utopiadev_django',
    }
}
```

# Project setup

Important note: Due to an error in django's libgeos module, a change needs to be made to one of the files before migrating the database.

The following file (replace virtualenv_name with the route to your virtualenv)

`virtualenv_name/lib/python2.7/site-packages/django/contrib/gis/geos/libgeos.py`

On the last function `geos_version_info` replace this:

`ver = geos_version().decode()`

with this

`ver = geos_version().decode().strip()`

After this was sorted out, use ``manage.py`` to run migrate and create all tables:

`(virtualenv_name) user@user-machine:~/projects/utopia-crm$ python manage.py migrate`


An output like this will appear:

```
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

and all tables should be created without any problem.

# Create a superuser to login into the application

Run the following command:

```
(virtualenv_name) user@user-machine:~/projects/utopia-crm$ python manage.py createsuperuser
```

And follow the prompts to create your super user.

WARNING: This user has ALL permissions on the application database. It is recommended that you only give superuser permissions to people you trust. It can be deleted if it's not necessary.

# Create the default groups and populate them with their permissions.

Run the following command, which will create the default groups for the application with some basic permissions.

```
(virtualenv_name) user@user-machine:~/projects/utopia-crm$ python manage.py loaddata fixtures/default_groups.json
```

# Running the application

Start the server by running:

```
(virtualenv_name) user@user-machine:~/projects/utopia-crm$ python manage.py runserver
```

and go to the following URL in your browser: http://127.0.0.1:8000/

# Troubleshooting

## psql error

* Error: django.db.utils.ProgrammingError: permission denied to create extension "postgis" HINT: Must be superuser to create this extension.

```
$ psql
=> \l            - list databases
=> \c <db name>  - connect to django db
=> create extension postgis;
```
