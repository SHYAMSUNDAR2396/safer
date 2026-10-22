from alembic import context
from dotenv import dotenv_values
from safer.config import Settings
from safer.models import Base
from sqlalchemy import create_engine, pool

url = Settings().database_url.get_secret_value()
if context.get_x_argument(as_dictionary=True).get("test") == "true":
    url = dotenv_values(".env")["TEST_DATABASE_URL"]
    if not url.endswith("/safer_test"):
        raise ValueError("Test migrations require the dedicated safer_test database")
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
