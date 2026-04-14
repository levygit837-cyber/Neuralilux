#!/bin/bash
set -e

# Create evolution user for Evolution API
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE USER evolution WITH PASSWORD 'Ev0lution_S3cur3_P@ssw0rd!';
EOSQL

# Create multiple databases if POSTGRES_MULTIPLE_DATABASES is set
if [ -n "$POSTGRES_MULTIPLE_DATABASES" ]; then
    echo "Creating multiple databases: $POSTGRES_MULTIPLE_DATABASES"
    for db in $(echo $POSTGRES_MULTIPLE_DATABASES | tr ',' ' '); do
        echo "Creating database: $db"
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
            CREATE DATABASE $db;
            GRANT ALL PRIVILEGES ON DATABASE $db TO $POSTGRES_USER;
            GRANT ALL PRIVILEGES ON DATABASE $db TO evolution;
EOSQL
        # Grant schema permissions for evolution database
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<-EOSQL
            GRANT ALL ON SCHEMA public TO evolution;
            GRANT USAGE ON SCHEMA public TO evolution;
            GRANT CREATE ON SCHEMA public TO evolution;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO evolution;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO evolution;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO evolution;
            ALTER DATABASE $db OWNER TO evolution;
EOSQL
        # Grant permissions on existing objects
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<-EOSQL
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO evolution;
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO evolution;
            GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO evolution;
EOSQL
    done
fi
