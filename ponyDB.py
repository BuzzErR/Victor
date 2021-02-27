from pony.orm import *


db = Database()


class File(db.Entity):
    id = PrimaryKey(int, auto=True)
    user_id = Required('User', reverse='files')
    telegram_file_id = Required(str)
    path = Required(str)
    password = Optional(str)
    name = Required(str)
    size = Required(int)


class User(db.Entity):
    Telegram_id_hash = PrimaryKey(str)
    capacity = Optional(int, default=True, sql_default='104857600')
    files = Set('File', cascade_delete=True, reverse='user_id')