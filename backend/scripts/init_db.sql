-- FraudShield — PostgreSQL Setup Script
-- Run as superuser: psql -U postgres -f init_db.sql

-- Create user and database
CREATE USER fraudshield_user WITH PASSWORD 'fraudshield_pass';
CREATE DATABASE fraudshield OWNER fraudshield_user;

-- Connect to the database
\c fraudshield

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE fraudshield TO fraudshield_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fraudshield_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fraudshield_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO fraudshield_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO fraudshield_user;
