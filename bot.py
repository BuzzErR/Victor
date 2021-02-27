import config
import telebot
import logging
import sqlite3
import time
from telebot import types
from hashlib import sha256
import encryption
import os
from pony.orm import *
from ponyDB import db, File, User

# db initializing

db.bind(provider='sqlite', filename='bot.db', create_db=True)
db.generate_mapping(create_tables=True)


def get_hash(string):
    return str(sha256(bytes(str(string), 'utf-8')).hexdigest())


def get_time():
    named_tuple = time.localtime()
    time_string = time.strftime("%m/%d/%Y, %H:%M:%S", named_tuple)
    return time_string


def does_user_exist(user_id):
    with db_session:
        if User.get(Telegram_id_hash=get_hash(user_id)) is not None:
            return True
        else:
            return False


# next-step functions


def pass_download(message):
    user_id_hash = get_hash(message.from_user.id)
    id_of_file = user_data[user_id_hash]
    with db_session:
        password = File[id_of_file].password
    if get_hash(message.text) == password:
        bot.delete_message(message.chat.id, message.message_id)
        bot.send_message(message.chat.id, 'Расшифровываю, подожди секунду')
        with db_session:
            path = File[id_of_file].path
        path_to_open = os.getcwd() + '/files/' + user_id_hash + '/' + path
        encryption.decrypt(path, path_to_open, str(message.from_user.id), message.text)
        markup = types.InlineKeyboardMarkup()
        btn_my_site = types.InlineKeyboardButton(text='Delete\U0001F5D1', callback_data='_deleteMessage_0')
        markup.add(btn_my_site)
        bot.send_document(chat_id=message.chat.id, data=open(path, 'rb'), reply_markup=markup)
        os.remove(path)

        bot.send_message(message.chat.id, 'Не забудь удалить сообщение от меня, расшифрованного файла я не '
                                          'сохранил.')
    else:
        bot.send_message(message.chat.id, 'Упс, пароль неверный, выбери файл заново и попробуй ещё раз')


def waiting_for_pass(message):
    password = str(message.text)
    with db_session:
        files = File.select(user_id=get_hash(message.from_user.id), password='')
        for file in files:
            path = file.path
            path_to_open = os.getcwd() + '/files/' + get_hash(message.from_user.id) + '/' + path

            encryption.encrypt(path_to_open, str(message.from_user.id), password)

            file.password = get_hash(password)

            commit()

    bot.send_message(message.chat.id, 'Отлично! Используй команду /all_files, чтобы посмотреть что у тебя есть')
    bot.delete_message(message.chat.id, message.message_id)


logging.basicConfig(filename=config.log_file_name, level=logging.ERROR)
user_data = {}

bot = telebot.TeleBot(config.token, threaded=False)
logging.info('Connected ' + get_time())


# main body and functions


@bot.message_handler(commands=['start'])
def start(message):
    logging.info('%s from %s', message.text, str(message.from_user.id) + ' ' + get_time())
    with db_session:
        if User.get(Telegram_id_hash=get_hash(message.from_user.id)) is not None:
            bot.send_message(message.chat.id, 'Рад видеть тебя снова')
        else:
            User(Telegram_id_hash=get_hash(message.from_user.id))

            path = os.getcwd() + '/files/' + get_hash(message.from_user.id)
            os.mkdir(path)

            logging.info('New user ' + message.from_user.first_name)
            bot.send_message(message.chat.id, 'Рад знакомству, ' + message.from_user.first_name + ', я Виктор')


@bot.message_handler(func=lambda message: not (does_user_exist(message.from_user.id)))
def reg_for_user(message):
    bot.send_message(message.chat.id, 'Мы не знакомы, выполни /start')


@bot.message_handler(content_types=['document'])
def download_file(message):
    logging.info('%s from %s', message.document.file_name, str(message.from_user.id) + ' ' + get_time())
    file_info = bot.get_file(message.document.file_id)
    with db_session:
        user = User.get(Telegram_id_hash=get_hash(message.from_user.id))
        size_of_all_files = sum(user.files.size)
    if size_of_all_files + message.document.file_size < 1024 * 1024 * 100:
        bot.send_message(message.chat.id, 'Подожди секунду, пока я скачаю твой файл')
        downloaded_file = bot.download_file(file_info.file_path)
        bot.delete_message(message.chat.id, message.message_id)
        with db_session:
            max_id = max(f.id for f in File)
        if max_id is None:
            max_id = 0
        new_path = message.document.file_name.split('.')
        user_id_hash = get_hash(message.from_user.id)
        path = os.getcwd() + '/files/' + user_id_hash
        file_name = new_path[0] + str(max_id + 1) + '.' + new_path[1]
        with open(path + '/' + file_name, 'wb') as new_file:
            new_file.write(downloaded_file)
        with db_session:
            f = File(telegram_file_id=message.document.file_id, path=file_name, password='', user_id=user_id_hash,
                     name=message.document.file_name, size=message.document.file_size)
            commit()
        bot.register_next_step_handler(message, waiting_for_pass)
        bot.send_message(message.chat.id, 'Отлично, теперь отправь '
                                          'мне пароль для шифровки файла, можешь отправить ещё файлов, но тогда'
                                          ' все они будут зашифрованы одним паролем')
    else:
        bot.send_message(message.chat.id, 'Прости, этот файл уже не влезет')
        bot.delete_message(message.chat.id, message.message_id)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        data = call.data.split('_')
        user_id_hash = get_hash(data[2])
        if data[1] == 'delete':
            with db_session:
                file = File[int(data[0])]
                path = file.path
                path = os.getcwd() + '/files/' + user_id_hash + '/' + path
                os.remove(path)
                File[int(data[0])].delete()
                commit()
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text='Deleted\u2705')

        if data[1] == 'send':
            bot.register_next_step_handler(call.message, pass_download)
            user_data[user_id_hash] = data[0]
            user_data[user_id_hash] = data[0]

            with db_session:
                name = File[int(data[0])].name
            bot.send_message(call.message.chat.id, 'Отправь мне пароль от ' + name)
    if data[1] == 'deleteMessage':
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)


@bot.message_handler(commands=['all_files'])
def send_list_of_files(message):
    with db_session:
        files = File.select(user_id=get_hash(message.from_user.id))
        for file in files:
            file_id = file.id
            name = file.name
            if file.password == '':
                name += '\nFILE IS UNENCRYPTED\u2757'
            markup = types.InlineKeyboardMarkup()
            btn_my_site1 = types.InlineKeyboardButton(text='Download\u2B07\uFE0F',
                                                      callback_data=str(file_id) + '_send_' +
                                                                    (str(message.from_user.id)))
            btn_my_site2 = types.InlineKeyboardButton(text='Delete\U0001F5D1',
                                                      callback_data=str(file_id) + '_delete_' +
                                                                    (str(message.from_user.id)))
            markup.add(btn_my_site1, btn_my_site2)
            bot.send_message(message.chat.id, name, reply_markup=markup)


if __name__ == '__main__':
    bot.polling(none_stop=True, timeout=123)()
