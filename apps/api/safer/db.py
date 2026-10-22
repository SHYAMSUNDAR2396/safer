from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request):
    with Session(request.app.state.engine, expire_on_commit=False) as db:
        yield db
