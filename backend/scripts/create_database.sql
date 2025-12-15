-- SQL script to create database and user for appointments system
-- Run this in pgAdmin Query Tool or psql

-- Create user (if doesn't exist)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'appointments_user') THEN
        CREATE USER appointments_user WITH PASSWORD 'Deep@123';
        RAISE NOTICE 'User appointments_user created';
    ELSE
        RAISE NOTICE 'User appointments_user already exists';
    END IF;
END
$$;

-- Create database (if doesn't exist)
SELECT 'CREATE DATABASE appointments_db OWNER appointments_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'appointments_db')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE appointments_db TO appointments_user;

-- Connect to database and grant schema privileges
\c appointments_db

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO appointments_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO appointments_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO appointments_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO appointments_user;

-- Verify
\du appointments_user
\l appointments_db

