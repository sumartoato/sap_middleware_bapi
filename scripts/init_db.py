"""Creates all Postgres tables. Run once before starting the app if you
are not using docker-compose (which the app also does automatically on
startup via the FastAPI lifespan handler)."""

from app.db.database import init_db

if __name__ == "__main__":
    init_db()
    print("Database tables created.")
