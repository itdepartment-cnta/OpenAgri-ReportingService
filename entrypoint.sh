#!/bin/bash

# Exit script on error
set -e


# Check whether these values have been passed
if [ -z "${REPORTING_POSTGRES_USER}" ]; then
  echo "Postgres username is not set in env"
  exit 1
fi

if [ -z "${REPORTING_POSTGRES_PASSWORD}" ]; then
  echo "Postgres password is not set in env"
  exit 1
fi

if [ -z "${REPORTING_POSTGRES_HOST}" ]; then
  echo "Postgres hostname is not set in env"
  exit 1
fi

if [ -z "${REPORTING_POSTGRES_PORT}" ]; then
  echo "Postgres port is not set in env"
  exit 1
fi

if [ -z "${REPORTING_POSTGRES_DB}" ]; then
  echo "Postgres database name is not set in env"
  exit 1
fi
# PARCHE CNTA: las credenciales de GateKeeper solo se exigen si se usa GateKeeper.
case "$(echo "${REPORTING_USING_GATEKEEPER:-true}" | tr '[:upper:]' '[:lower:]')" in
  true|1|yes|on)
    for var in REPORTING_GATEKEEPER_BASE_URL REPORTING_GATEKEEPER_USERNAME REPORTING_GATEKEEPER_PASSWORD; do
      if [ -z "${!var}" ]; then
        echo "$var is not set in env (required when REPORTING_USING_GATEKEEPER is enabled)"
        exit 1
      fi
    done
    ;;
esac
if [ -z "${REPORTING_BACKEND_CORS_ORIGINS}" ]; then
  echo "Cors is not set in env"
  exit 1
fi


# PARCHE CNTA: la URL de conexion la construye alembic/env.py desde la configuracion
# (antes, un sed sobre alembic.ini que fallaba con '/' o '&' en la contrasena).


# Migrate sqlalchemy models to postgres via alembic
echo "Starting db migrations"

alembic upgrade head

echo "Finished db migrations"


# Start the FastAPI app with uvicorn
echo "Starting Uvicorn server"

exec uvicorn --host 0.0.0.0 --port "$1" --app-dir=app 'main:app'

echo "Started Uvicorn server"