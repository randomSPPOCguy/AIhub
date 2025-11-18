# Database Directory

This directory will contain the SQLite database file after running the migration.

## Setup

1. The database file `music.sqlite` will be created automatically when you run:
   ```bash
   npm run migrate
   ```

2. The database is excluded from git via `.gitignore` to prevent committing user data.

## Schema

See `src/db/schema.sql` for the database schema definition.
