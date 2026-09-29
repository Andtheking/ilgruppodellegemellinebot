#!/bin/bash

# Controlla se è stato passato il parametro con il nome della migrazione
if [ -z "$1" ]; then
  echo "No migration name given." >&2
  echo "Usage: ./make_migration.sh migration_name" >&2
  exit 1
fi

MIGRATION_NAME=$1

echo "Creating migration: $MIGRATION_NAME..."

if pw_migrate create "$MIGRATION_NAME" \
  --database sqlite:///secret/Database.db \
  --directory models/migrations/ \
  --auto \
  --auto-source models.models; then
  
  echo "'$MIGRATION_NAME' created successfully"
else
  echo "Error with pw_migrate." >&2
  exit 1
fi