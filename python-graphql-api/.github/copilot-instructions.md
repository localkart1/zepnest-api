# Python GraphQL API - Development Guide

## Project Setup

This is a Python Flask API with GraphQL support and SQLAlchemy ORM.

## Quick Commands

### Development
```bash
python3 main.py
```
Starts the server on http://localhost:5002

### Database
Tables are created automatically on startup.

### GraphQL Endpoint
- **Query/Mutation**: POST http://localhost:5002/graphql
- **GraphiQL IDE**: GET http://localhost:5002/graphql

## Key Files

- `api/__init__.py` - Flask app factory and database setup
- `api/models/` - Database models (User, Post)
- `api/graphql/schema.py` - GraphQL queries and mutations
- `main.py` - Application entry point
- `.env` - Environment variables

## Adding Features

### New Model
1. Create file in `api/models/`
2. Define SQLAlchemy model
3. Import in `api/__init__.py`

### New GraphQL Type
1. Add class in `api/graphql/types.py`
2. Add resolver methods

### New Mutation
1. Create mutation class in `api/graphql/mutations.py`
2. Add to `Mutation` class in `api/graphql/schema.py`

## Testing Queries

Use the GraphiQL IDE at http://localhost:5002/graphql or curl:

```bash
curl -X POST http://localhost:5002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ users { id name email } }"}'
```

## Environment Variables

- `FLASK_ENV` - development/production
- `FLASK_DEBUG` - True/False for debug mode
- `DATABASE_URL` - SQLite path
- `PORT` - Server port (default 5002)

## Troubleshooting

**Port already in use?**
Change PORT in .env file

**Database issue?**
Delete `app.db` and restart (tables recreate automatically)

**GraphQL query error?**
Check GraphiQL IDE for error details
