# Database Directory

This directory is used to store the SQLite database files for AIhub.

## Note

Database files are excluded from Git for security and performance reasons. When you clone this repository, you will need to:

1. Create a new database file by running the application
2. Or restore a backup database file if you have one

## Database Files

The main database file that will be created here is:
- `music.sqlite` - Contains API keys, user data, and application state

## Database Structure

The database contains tables for:
- API keys
- User profiles
- Music information
- Application configuration