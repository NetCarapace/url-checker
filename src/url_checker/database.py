#!/usr/bin/env python3
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


sql_db_conn = SQLAlchemy(model_class=Base)
migrate_db = Migrate()
