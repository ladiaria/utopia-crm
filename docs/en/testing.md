# Testing

1. Database setup

When running tests, Django will try to create a new database for testing purposes and create the `postgis` extension on it, this will fail if the Postgres user is the default unprivileged user created using the `INSTALL.md` steps. To solve this issue you have to follow [this instructions](https://stackoverflow.com/a/59074119/2292933) and choose one of the methods described there.

2. Running included tests

With the virtualenv activated, execute the script `runtests.sh`.

