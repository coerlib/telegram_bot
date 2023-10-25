import re
from datetime import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.exceptions import MessageToDeleteNotFound

from config import API_TOKEN

from requests import *

storage = MemoryStorage()
bot = Bot(API_TOKEN)
dp = Dispatcher(bot, storage=storage)


# функции
async def get_doctors_buttons() -> InlineKeyboardMarkup:
    doctors = await get_doctors()
    buttons = []
    if doctors:
        for doctor in doctors:
            buttons.append(
                InlineKeyboardButton(text=doctor['full_name'], callback_data=f"set_doctor_{doctor['user_id']}"))
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(*buttons)
        return keyboard
    return -1


async def combine_chats(available_chats, current_chats):
    combined_chats = []

    for available_chat in available_chats:
        user_id = available_chat
        found_chat = None
        for chat in current_chats:
            if chat['interlocutor_id'] == user_id:
                found_chat = chat
                break
        if found_chat:
            combined_chats.append(found_chat)
        else:
            new_chat_info = {
                'user_id': user_id,
                'interlocutor_id': user_id,
                'last_date': "-",
                'last_message': 'Новый чат',
                'new': "-"
            }
            combined_chats.append(new_chat_info)

    return combined_chats


# состояния
class PatientProfileStatesGroup(StatesGroup):
    fullName = State()
    text = State()


async def on_start_up(_):
    await db_start()


# команды

@dp.message_handler(commands=['test'])
async def test(message: types.Message, state: FSMContext):
    chat = await get_chat2(message.from_user.id, await get_current_user_id(message.from_user.id))
    for message in chat:
        print(message)


@dp.message_handler(commands=['cancel'], state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.finish()
    sent_message = await bot.send_message(message.chat.id, "Команда отменена")
    await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'отменена команды', '', '', 'bot',
                      message.chat.id, 0)
    await bot.delete_message(message.chat.id, message.message_id)


@dp.message_handler(commands=['id'])
async def send_chat_history(message: types.Message):
    print(message.from_user.id)
    text = f"<code>{message.from_user.id}</code>"
    await bot.send_message(message.from_user.id, text, parse_mode='HTML')


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    kb = [
        [
            types.KeyboardButton(text="пациенты без врачей"),
        ],
        [
            types.KeyboardButton(text="К чатам"),
        ],
    ]
    keyboardAdmin = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    kb = [
        [
            types.KeyboardButton(text="К чатам"),
        ],
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    if await is_new_patient(message.from_user.id):
        sent_message = await bot.send_message(message.chat.id, f"Добрый день! Напишите ваше ФИО")
        await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'запрос имени', '', '', 'bot',
                          message.chat.id, 0)

        await PatientProfileStatesGroup.fullName.set()
    else:
        if await get_role_by_id(message.from_user.id) == 'admin':
            sent_message = await bot.send_message(message.from_user.id, "Привет, администратор!", reply_markup=keyboardAdmin)
            await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'приветствие', '', '', 'bot',
                      message.chat.id, 0)
            # await message.reply("Привет, администратор!", reply_markup=keyboard)
        elif await get_role_by_id(message.from_user.id) == 'doctor':
            sent_message = await bot.send_message(message.from_user.id, "Привет, доктор!", reply_markup=keyboard)
            await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'приветствие', '', '', 'bot',
                      message.chat.id, 0)

    await bot.delete_message(message.chat.id, message.message_id)


@dp.message_handler(commands=['delete'])
async def delete_message(message: types.Message):
    messages = await get_message_ids_by_chat_id(message.chat.id)
    if messages and len(messages) > 0:
        for message_id in messages:
            try:
                await bot.delete_message(message.chat.id, message_id)
                await set_display_status(message_id)
            except MessageToDeleteNotFound:
                print(f"Сообщение {message_id} не найдено и не может быть удалено.")
            except Exception as e:
                print(f"Ошибка при удалении сообщения {message_id}: {e}")
    try:
        await bot.delete_message(message.chat.id, message.message_id)
    except MessageToDeleteNotFound:
            print(f"Сообщение {message.message_id} не найдено и не может быть удалено.")
    except Exception as e:
        print(f"Ошибка при удалении сообщения {message.message_id}: {e}")


@dp.message_handler(commands=['chat'])
async def show_chats(message: types.Message):
    user_id = message.from_user.id
    role = await get_role_by_id(user_id)
    chats = []
    
    chats = await get_chats(user_id, role)

    await delete_message(message)
    await set_current_user_id(user_id, '')
    if chats:

        # chats.sort(key=lambda x: datetime.strptime(x['last_date'], "%Y-%m-%d %H:%M:%S"), reverse=False) #сортировка по дате
        def custom_key(item):
            if item['last_date'] != "-":
                return datetime.strptime(item['last_date'], "%Y-%m-%d %H:%M:%S")
            else:
                return datetime.min  # Помещаем элементы с "-" в конец

        chats.sort(key=custom_key, reverse=False)

        chatBtn = [
            [
                types.KeyboardButton(text="К чатам"),
            ],
        ]
        keyboardСhatBtn = types.ReplyKeyboardMarkup(keyboard=chatBtn, resize_keyboard=True)
        sent_message = await bot.send_message(chat_id=message.chat.id, text="Выберите, с кем будете общаться", reply_markup=keyboardСhatBtn)
        
        await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'вывод чатов', '', '', 'bot',
                            message.chat.id, 0)

        for chat in chats:
            interlocutor_role = await get_role_by_id(chat['interlocutor'])
            smile = "👨 "
            if interlocutor_role == 'admin':
                smile = "💼 "
            elif interlocutor_role == 'doctor':
                smile = "👨‍⚕️ "
            chat_name = f"{smile}{await get_full_name_by_id(chat['interlocutor'])}"

            if str(chat['user_id']) == "-":
                last_user = "-"
            elif str(user_id) == str(chat['user_id']):
                last_user = "вы"
            else:
                last_user = await get_full_name_by_id(chat['user_id'])

            date = chat['last_date']
            text = chat['last_message']
            new_message = chat['new_message']

            message_text = f"Чат с  {chat_name}\n\nПоследнее сообщение от: {last_user}\nТекст сообщения: {text}\nДата и время: {date}"
            if new_message == 1:
                message_text += "\nЕсть новые сообщения‼️"

            inline_button = InlineKeyboardButton("Выбрать этот чат", callback_data=f"choose_chat_{chat['interlocutor']}")
            keyboard = InlineKeyboardMarkup().add(inline_button)

            sent_message = await bot.send_message(chat_id=user_id, text=message_text, reply_markup=keyboard)
            await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'вывод чатов', '', '', 'bot', user_id, 0)
    else:
        chatBtn = [
            [
                types.KeyboardButton(text="К чатам"),
            ],
        ]
        keyboardСhatBtn = types.ReplyKeyboardMarkup(keyboard=chatBtn, resize_keyboard=True)

        sent_message = await bot.send_message(chat_id=message.chat.id, text="Доступных чатов пока нет. Ваши сообщения видит только администратор", 
                                              reply_markup=keyboardСhatBtn)
        await set_message(sent_message.message_id, sent_message.chat.id, 'service', '', '', '', 'bot',
                            message.chat.id, 0)
        

@dp.message_handler(commands=['admins'])
async def show_admins(message: types.Message):
    if (await is_main_admin(message.from_user.id)):
        admins = await get_admins()

        if not admins:
            sent_message = await bot.send_message(message.chat.id, text="Список админов пуст")
            await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'Список админов пуст', '', '', 'bot',
                            message.chat.id, 0)
            return
        
        for admin in admins:
            # Создаем кнопку для удаления админа с callback_data, содержащим id админа
            inline_button = InlineKeyboardButton(f"Удалить админа {admin}", callback_data=f"delete_admin_{admin}")
            keyboard = InlineKeyboardMarkup().add(inline_button)

            sent_message = await bot.send_message(message.chat.id, text=f"Админ {admin}", reply_markup=keyboard)
            await set_message(sent_message.message_id, sent_message.chat.id, 'service', f'вывод админов', '', '', 'bot',
                            message.chat.id, 0)


@dp.message_handler(commands=['doctors'])
async def show_doctors(message: types.Message):
    if (await is_main_admin(message.from_user.id)):
        doctors = await get_doctors()

        if not doctors:
            sent_message = await bot.send_message(message.chat.id, text="Список врачей пуст")
            await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'Список врачей пуст', '', '', 'bot',
                            message.chat.id, 0)
            return
        
        for doctor in doctors:
            # Создаем кнопку для удаления врача с callback_data, содержащим id врача
            inline_button = InlineKeyboardButton(f"Удалить врача {await get_full_name_by_id(doctor)}", callback_data=f"delete_doctor_{doctor}")
            keyboard = InlineKeyboardMarkup().add(inline_button)

            sent_message = await bot.send_message(message.chat.id, text=f"Врач {await get_full_name_by_id(doctor)}", reply_markup=keyboard)
            await set_message(sent_message.message_id, sent_message.chat.id, 'service', f'вывод врачей', '', '', 'bot',
                            message.chat.id, 0)

# события
@dp.message_handler(lambda message: message.text == 'пациенты без врачей')
async def send_patients_with_buttons(message: types.Message):
    await set_message(message.message_id, message.chat.id, 'service', '', '', '', 'bot', message.chat.id, 0)

    patients = await get_patients_without_doctor()

    if not patients:
        sent_message = await bot.send_message(chat_id=message.chat.id, text="Все пациенты имеют назначенных врачей")
        await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'Все пациенты имеют назначенных врачей', '',
                          '', 'bot',
                          message.chat.id, 0)
        return

    for patient in patients:
        full_name = patient['full_name']

        text = f"#{patient['user_id']}\nПациент: {full_name}\nВрач: не назначен"
        inline_button = InlineKeyboardButton("Назначить врача", callback_data=f"add_doctor_{patient['user_id']}")

        keyboard = InlineKeyboardMarkup().add(inline_button)

        sent_message = await bot.send_message(chat_id=message.chat.id, text=text, reply_markup=keyboard)
        await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'вывод пациентов без врачей', '',
                          '', 'bot',
                          message.chat.id, 0)
        

@dp.message_handler(lambda message: message.text == 'К чатам')
async def send_patients_with_buttons(message: types.Message):
    await show_chats(message)
    

# обработчики кнопок
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('delete_admin_'))
async def process_delete_admin(callback_query: CallbackQuery):
    admin_id = callback_query.data.split('_')[-1]
    
    # Ваш код для удаления админа по admin_id
    await delete_admin_by_id(admin_id)
    
    # Отправляем уведомление о том, что админ удален
    sent_message = await bot.send_message(callback_query.message.chat.id, f"Админ {admin_id} удален")
    await set_message(sent_message.message_id, sent_message.chat.id, 'service', f'Админ {admin_id} удален', '', '', 'bot',
                      callback_query.message.chat.id, 0)
    await bot.answer_callback_query(callback_query.id, f"")


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('delete_doctor_'))
async def process_delete_doctor(callback_query: CallbackQuery):
    doctor_id = callback_query.data.split('_')[-1]
    name = await get_full_name_by_id(doctor_id)
    
    # Ваш код для удаления админа по admin_id
    await delete_doctor_by_id(doctor_id)
    await delete_patient_doctor(doctor_id)
    
    # Отправляем уведомление о том, что админ удален
    sent_message = await bot.send_message(callback_query.message.chat.id, f"Врач {name} удален")
    await set_message(sent_message.message_id, sent_message.chat.id, 'service', f'Врач {name} удален', '', '', 'bot',
                      callback_query.message.chat.id, 0)
    await bot.answer_callback_query(callback_query.id, f"")


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('add_doctor_'))
async def process_add_doctor(callback_query: CallbackQuery):
    patient_id = callback_query.data.split('_')[-1]

    buttons = await get_doctors_buttons()
    if buttons != -1:
        sent_message = await bot.send_message(chat_id=callback_query.message.chat.id, text=f"Выберите врача для пациента {patient_id}",
                               reply_markup=await get_doctors_buttons())
        await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'Выберите врача для пациента', '', '',
                          'bot', callback_query.message.chat.id, 0)

    else:
        await bot.send_message(chat_id=callback_query.message.chat.id, text=f"Нет врачей")
    await bot.answer_callback_query(callback_query.id, text=f"")


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('set_doctor_'))
async def process_set_doctor(callback_query: CallbackQuery, state: FSMContext):
    patient_id = callback_query.message.text.split(' ')[-1]
    doctor_id = callback_query.data.split('_')[-1]

    await set_doctor(patient_id, doctor_id)

    sent_message = await bot.send_message(chat_id=callback_query.message.chat.id, text=f"Врач успешно назначен для пациента")
    await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'Врач успешно назначен для пациента', '', '',
                      'bot', callback_query.message.chat.id, 0)
    sent_message = await bot.send_message(patient_id, f"Вам назначен врач: {await get_full_name_by_id(doctor_id)}")
    await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'Вам назначен врач', '', '',
                      'bot', patient_id, 0)
    sent_message = await bot.send_message(doctor_id, f"#{patient_id}\nВам назначен пациент: {await get_full_name_by_id(patient_id)}")
    await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'Вам назначен пациент', '', '',
                      'bot', doctor_id, 0)
    await bot.answer_callback_query(callback_query.id, f"")


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('choose_chat_'))
async def process_set_doctor(callback_query: CallbackQuery, state: FSMContext):
    current_user = callback_query.data.split('_')[-1]
    await set_current_user_id(callback_query.message.chat.id, current_user)

    await delete_message(callback_query.message)

    history = f""
    user_id = callback_query.message.chat.id
    chat = await get_chat2(user_id, await get_current_user_id(user_id))

    new_messages = []
    if chat:
        for message in chat:
            if message['new_message'] == 0:
                role = await get_role_by_id(message['from_user'])
                smile = "👨 "
                if role == 'admin':
                    smile = "💼 "
                elif role == 'doctor':
                    smile = "👨‍⚕️ "
                
                message_text = f"{smile}"
                if message['from_user'] == str(user_id):
                    message_text += "Вы: "
                else:
                    message_text += f"{await get_full_name_by_id(await get_current_user_id(user_id))}: "
                    
                if message['type'] == 'text':
                    message_text += f"{message['text']}\n\n"
                elif message['type'] == 'photo':
                    if message['text'] and len(message['text']) > 0:
                        message_text += f"{message['text']}\n\n"
                    else:
                        message_text += "(фото без текста)"

                history += message_text
            else:
                new_messages.append(message)
    else:
        history = 'Начать чат'

    if history and len(history):
        sent_message = await bot.send_message(chat_id=callback_query.message.chat.id,
                                            text=f"{history}")
        await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'история переписки', '', '',
                        'bot', callback_query.message.chat.id, 0)
                      
    
    if new_messages and len(new_messages) > 0: #todo тут могут отправляться фотки еще
        sent_message = await bot.send_message(chat_id=callback_query.message.chat.id,
                                          text=f"⬇️Новые сообщения⬇️")
        await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'история переписки', '', '',
                        'bot', callback_query.message.chat.id, 0)
        
        for new_message in new_messages:
            sent_message = await bot.send_message(chat_id=callback_query.message.chat.id,
                                          text=f"{new_message['text']}")
            await set_readability(new_message['message_id'])
            # убираем значок нового сообщения
            await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'история переписки', '', '',
                      'bot', callback_query.message.chat.id, 0)
            
    chatBtn = [
        [
            types.KeyboardButton(text="К чатам"),
        ],
    ]
    keyboardСhatBtn = types.ReplyKeyboardMarkup(keyboard=chatBtn, resize_keyboard=True)
    sent_message = await bot.send_message(chat_id=callback_query.message.chat.id,
                                          text=f" -- Выбран чат с {await get_full_name_by_id(current_user)}", reply_markup=keyboardСhatBtn)
    
    await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'выбран чат', '', '',
                      'bot', callback_query.message.chat.id, 0)
    await bot.answer_callback_query(callback_query.id, f"")


# состояния
@dp.message_handler(state=PatientProfileStatesGroup.fullName)
async def process_fio(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data['full_name'] = message.text
        data['user_id'] = message.chat.id

        await set_message(message.message_id, message.chat.id, message.content_type, message.text, '', message.date,
            message.from_user.id, 'bot', 0)

    sent_message = await bot.send_message(message.chat.id, f"Напишите ваше сообщение")
    await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'первая жалоба', '', '', 'bot',
                      message.chat.id, 0)
    await PatientProfileStatesGroup.next()


@dp.message_handler(state=PatientProfileStatesGroup.text)
async def process_text(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data['text'] = message.text
        await create_patient(data["user_id"], data["full_name"])

        await set_message(message.message_id, message.chat.id, message.content_type, message.text, '', message.date,
                              message.from_user.id, 'bot', 0)

        chatBtn = [
            [
                types.KeyboardButton(text="К чатам"),
            ],
        ]
        keyboardСhatBtn = types.ReplyKeyboardMarkup(keyboard=chatBtn, resize_keyboard=True)
        sent_message = await bot.send_message(message.from_user.id, "Спасибо! С вами свяжется администратор", reply_markup=keyboardСhatBtn)

        await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'свяжется администратор', '', '', 'bot',
                          message.chat.id, 0)

        for admin in await get_admins():
            sent_message = await bot.send_message(admin,
                                   f"Новый пользователь!!!\n\n#{message.from_user.id}\n👨 {await get_full_name_by_id(message.from_user.id)}\n\n{message.text}")
            await set_message(sent_message.message_id, sent_message.chat.id, 'service', 'Новый пользователь', '',
                              '', 'bot', message.chat.id, 0)


    await state.finish()


# сообщения
@dp.message_handler(content_types=["text", "photo"])
async def send_message(message: types.Message):
    current_user = await get_current_user_id(message.from_user.id)
    from_user = message.from_user.id
    to_user = current_user

    role = await get_role_by_id(from_user)

    if message.photo:
        photo_caption = message.caption if message.caption else ''  # Получаем подпись у фотографии, если есть
        if role == "patient":
            message_text = f"👨 {await get_full_name_by_id(from_user)}\n\n{photo_caption}"
        elif role == "doctor":
            message_text = f"👨‍⚕️ {await get_full_name_by_id(from_user)}\n\n{photo_caption}"
        elif role == "admin":
            message_text = f"💼 администратор\n\n{photo_caption}"
    else:
        if role == "patient":
            message_text = f"👨 {await get_full_name_by_id(from_user)}\n\n{message.text}"
        elif role == "doctor":
            message_text = f"👨‍⚕️ {await get_full_name_by_id(from_user)}\n\n{message.text}"
        elif role == "admin":
            message_text = f"💼 администратор\n\n{message.text}"

    if role == "patient" or role == "doctor" or role == "admin":
        if message.photo:  # Если это фотография
            photo = message.photo[-1]  # Получаем последний доступный размер фотографии
            photo_link = photo.file_id  # Ссылка на фото

            new_message = 0 
            if str(await get_current_user_id(to_user)) != str(from_user): # общается ли человек сейчас с кем-то или нет
                new_message = 1

            if to_user:
                await set_message(message.message_id, message.chat.id, 'photo', photo_caption, photo_link, message.date,
                              from_user, to_user, new_message)
            else:
                await set_message(message.message_id, message.chat.id, 'photo', photo_caption, photo_link, message.date,
                              from_user, 'admin', new_message)

            if to_user:
                if new_message == 0:
                    sent_message = await bot.send_photo(to_user, photo.file_id, caption=message_text)
                    await set_message(sent_message.message_id, sent_message.chat.id, 'service', message_text, '', sent_message.date,
                                    'bot', to_user, 0) #todo добавить1
                else:
                    sent_message = await bot.send_message(to_user, "Новое сообщение от другого пользователя")
                    await set_message(sent_message.message_id, sent_message.chat.id, 'service', "уведомление", '', sent_message.date,
                                  'bot', to_user, 0) #todo добавить1

            else:
                for admin in await get_admins():
                    sent_message = await bot.send_photo(admin, photo.file_id, caption=message_text)
                    await set_message(sent_message.message_id, sent_message.chat.id, 'service', message_text, '', sent_message.date,
                                      'bot', admin, 0) #todo добавить1
        else:  # Если это обычное текстовое сообщение
            new_message = 0 
            if str(await get_current_user_id(to_user)) != str(from_user): # общается ли человек сейчас с кем-то или нет
                new_message = 1

            if to_user:
                await set_message(message.message_id, message.chat.id, 'text', message.text, '', message.date,
                              from_user, to_user, new_message)
            else:
                await set_message(message.message_id, message.chat.id, 'text', message.text, '', message.date,
                              from_user, 'admin', new_message)

            if to_user:
                if new_message == 0:
                    sent_message = await bot.send_message(to_user, message_text)
                    await set_message(sent_message.message_id, sent_message.chat.id, 'service', message_text, '', sent_message.date,
                                  'bot', to_user, 0) #todo добавить1
                else:
                    sent_message = await bot.send_message(to_user, "Новое сообщение от другого пользователя")
                    await set_message(sent_message.message_id, sent_message.chat.id, 'service', "уведомление", '', sent_message.date,
                                  'bot', to_user, 0) #todo добавить1
            else:
                for admin in await get_admins():                    
                    sent_message = await bot.send_message(admin, message_text)
                    await set_message(sent_message.message_id, sent_message.chat.id, 'service', message_text, '', sent_message.date,
                                      'bot', admin, 0) #todo добавить1
    else:
        print('Нет такого пользователя')


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_start_up)
