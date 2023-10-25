import sqlite3 as sq


async def db_start():
    global db, cur

    db = sq.connect('communications.db')
    cur = db.cursor()

    # Создание таблицы пациентов
    cur.execute("CREATE TABLE IF NOT EXISTS patient(user_id TEXT PRIMARY KEY, full_name TEXT, current_user_id TEXT)")
    db.commit()

    # Создание таблицы администраторов
    cur.execute("CREATE TABLE IF NOT EXISTS admin(user_id TEXT PRIMARY KEY, current_user_id TEXT)")
    db.commit()

    # Создание таблицы главного администратора
    cur.execute("CREATE TABLE IF NOT EXISTS main_admin(user_id TEXT PRIMARY KEY)")
    db.commit()

    # Создание таблицы связей докторов и пациентов
    cur.execute("CREATE TABLE IF NOT EXISTS patient_doctor(patient_id TEXT, doctor_id TEXT)")
    db.commit()

    # Создание таблицы докторов
    cur.execute("CREATE TABLE IF NOT EXISTS doctor(user_id TEXT PRIMARY KEY, full_name TEXT, current_user_id TEXT)")
    db.commit()

    # Создание таблицы сообщений
    cur.execute(
        "CREATE TABLE IF NOT EXISTS message(message_id INTEGER, chat_id INTEGER, type TEXT, text TEXT, photo TEXT, "
        "date TEXT, from_user TEXT, to_user TEXT, display INTEGER, new_message INTEGER)")
    db.commit()

    print("База данных готова к работе")


# геттеры
async def get_role_by_id(user_id: str):
    try:
        cur.execute("SELECT * FROM admin WHERE user_id = ?", (user_id,))
        admin = cur.fetchone()
        if admin:
            return "admin"

        cur.execute("SELECT * FROM patient WHERE user_id = ?", (user_id,))
        patient = cur.fetchone()
        if patient:
            return "patient"

        cur.execute("SELECT * FROM doctor WHERE user_id = ?", (user_id,))
        doctor = cur.fetchone()
        if doctor:
            return "doctor"

        return None

    except Exception as e:
        print(f"Ошибка получения роли пользователя: {e}")
        return None


async def get_patients_without_doctor():
    try:
        cur.execute("""
                    SELECT user_id, full_name 
                    FROM patient 
                    WHERE user_id NOT IN (SELECT patient_id FROM patient_doctor)
                """)

        rows = cur.fetchall()
        patients = []
        for row in rows:
            patient = {"user_id": row[0], "full_name": row[1]}
            patients.append(patient)
        return patients
    except Exception as e:
        print(f"Ошибка получения пациентов без врача: {e}")


async def get_doctors():
    try:
        cur.execute("SELECT * FROM doctor")
        rows = cur.fetchall()
        doctors = []
        for row in rows:
            patient = {"user_id": row[0], "full_name": row[1]}
            doctors.append(patient)
        return doctors
    except Exception as e:
        print(f"Ошибка получения врачей: {e}")


async def get_full_name_by_id(user_id: str):
    role = await get_role_by_id(user_id)

    if role == "patient":
        cur.execute("SELECT full_name FROM patient WHERE user_id = ?", (user_id,))
    elif role == "doctor":
        cur.execute("SELECT full_name FROM doctor WHERE user_id = ?", (user_id,))
    else:
        return None
    result = cur.fetchone()
    return result[0] if result else None


async def get_current_user_id(user_id: str):
    role = await get_role_by_id(user_id)

    try:
        if role == "patient":
            cur.execute("SELECT current_user_id FROM patient WHERE user_id = ?", (user_id,))
        elif role == "admin":
            cur.execute("SELECT current_user_id FROM admin WHERE user_id = ?", (user_id,))
        elif role == "doctor":
            cur.execute("SELECT current_user_id FROM doctor WHERE user_id = ?", (user_id,))

        current_user_id = cur.fetchone()

        if current_user_id:
            return current_user_id[0]
        else:
            return -1
    except Exception as e:
        print(f"Ошибка при получении текущего пользователя для пользователя: {e}")
        return -1


async def get_message_ids_by_chat_id(chat_id):
    try:
        cur.execute("SELECT message_id FROM message WHERE chat_id = ? AND display = 1", (chat_id,))
        rows = cur.fetchall()
        message_ids = [row[0] for row in rows]
        return message_ids
    except Exception as e:
        print(f"Ошибка при получении ID сообщений: {e}")
        return []


# async def get_chats(user_id: str):
#     try:
#         cur.execute("""
#             SELECT
#                 m.message_id,
#                 m.from_user,
#                 m.to_user,
#                 m.date,
#                 m.text,
#                 m.display
#             FROM
#                 message m
#             WHERE
#                 (m.from_user = ? OR m.to_user = ?) AND m.type <> 'service' AND m.message_id IN (
#                     SELECT
#                         MAX(message_id) AS message_id
#                     FROM
#                         message
#                     WHERE
#                         from_user = ? OR to_user = ?
#                     GROUP BY
#                         CASE
#                             WHEN from_user = ? THEN to_user
#                             ELSE from_user
#                         END
#                 )
#             ORDER BY
#                 m.date DESC
#         """, (user_id, user_id, user_id, user_id, user_id))

#         rows = cur.fetchall()
#         chats = []
#         for row in rows:
#             chat = {}
#             chat['user_id'] = row[2] if row[1] == user_id else row[1]
#             if str(row[1]) == str(user_id):
#                 chat['interlocutor_id'] = row[2]
#             else:
#                 chat['interlocutor_id'] = row[1]

#             chat['last_date'] = row[3]
#             chat['last_message'] = row[4]
#             chat['new'] = row[5]
#             chats.append(chat)
#         return chats
#     except Exception as e:
#         print(f"Ошибка при получении чатов: {e}")
#         return []
    


# start
async def get_chats(user_id: str, role):
    try:
        chats = []

        if role == 'patient':
            cur.execute("SELECT doctor_id FROM patient_doctor WHERE patient_id = ?", (user_id,))
        elif role == 'doctor':
            cur.execute("SELECT patient_id FROM patient_doctor WHERE doctor_id = ?", (user_id,))
        elif role == 'admin':
            cur.execute("SELECT user_id FROM patient UNION SELECT user_id FROM doctor")
        people = cur.fetchall()

        for man in people:
            man = man[0]

            # Ищем подходящие записи из таблицы message
            cur.execute("""
                SELECT m.text, m.from_user, m.to_user, m.date, m.new_message
                FROM message m
                WHERE (m.from_user = ? AND m.to_user = ? OR m.from_user = ? AND m.to_user = ?)
                    AND m.type <> 'service'
                ORDER BY m.date DESC
                LIMIT 1
            """, (user_id, man, man, user_id))

            row = cur.fetchone()

            if row:
                chat = {}
                chat['user_id'] = row[1]
                if str(row[1]) == str(user_id):
                    chat['interlocutor'] = row[2]
                elif str(row[2]) == str(user_id):
                    chat['interlocutor'] = row[1]
                chat['last_date'] = row[3]
                chat['last_message'] = row[0]
                chat['new_message'] = row[4]
                chats.append(chat)
            else:
                chat = {}
                chat['user_id'] = "-"
                chat['interlocutor'] = man
                chat['last_date'] = "-"
                chat['last_message'] = "-"
                chat['new_message'] = 0
                chats.append(chat)

        return chats

    except Exception as e:
        print(f"Ошибка при получении чатов: {e}")
        return []

# end




# start
async def get_chat2(user_id: str, current_user: str):
    try:
        cur.execute("""
            SELECT type, text, photo, from_user, to_user, new_message, message_id
            FROM message
            WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
            ORDER BY date
        """, (user_id, current_user, current_user, user_id))

        messages = []
        for row in cur.fetchall():
            message = {
                'type': row[0],
                'text': row[1],
                'photo': row[2],
                'from_user': row[3],
                'to_user': row[4],
                'new_message': row[5],
                'message_id': row[6]
            }
            messages.append(message)

        return messages
    
    except Exception as e:
        print(f"Ошибка при получении диалога: {e}")
        return []
# end


async def get_chat(user_id: str, current_user: str):
    try:
        cur.execute("""
            SELECT 
                message_id, chat_id, type, text, photo, date, from_user, to_user, display
            FROM 
                message
            WHERE 
                (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
            ORDER BY 
                date ASC
        """, (user_id, current_user, current_user, user_id))

        rows = cur.fetchall()
        dialog = []
        for row in rows:
            message = {
                "message_id": row[0],
                "chat_id": row[1],
                "type": row[2],
                "text": row[3],
                "photo": row[4],
                "date": row[5],
                "from_user": row[6],
                "to_user": row[7],
                "display": row[8]
            }
            dialog.append(message)
        return dialog
    except Exception as e:
        print(f"Ошибка при получении диалога: {e}")
        return []


async def get_admins():
    try:
        cur.execute("SELECT user_id FROM admin")
        rows = cur.fetchall()
        admins = []
        for row in rows:
            admins.append(row[0])
        return admins
    except Exception as e:
        print(f"Ошибка получения администраторов: {e}")


# todo получить чаты для пациентов и докторов
async def get_doctors_chats(user_id: str):
    try:
        cur.execute("SELECT DISTINCT doctor_id FROM patient_doctor WHERE patient_id = ?", (user_id,))
        rows = cur.fetchall()
        doctors_chats = [row[0] for row in rows]
        return doctors_chats
    except Exception as e:
        print(f"Ошибка при получении пользователей, с которыми общается {user_id}: {e}")
        return []


async def get_patients_chats(user_id: str):
    try:
        cur.execute("SELECT DISTINCT patient_id FROM patient_doctor WHERE doctor_id = ?", (user_id,))
        rows = cur.fetchall()
        patients_chats = [row[0] for row in rows]
        return patients_chats
    except Exception as e:
        print(f"Ошибка при получении пользователей, с которыми общается {user_id}: {e}")
        return []


async def get_for_admins_chats():
    try:
        cur.execute("SELECT user_id FROM patient")
        patient_ids = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT user_id FROM doctor")
        doctor_ids = [row[0] for row in cur.fetchall()]
        all_user_ids = patient_ids + doctor_ids
        return all_user_ids
    except Exception as e:
        print(f"Ошибка при получении всех пользователей для администратора: {e}")
        return []
    

async def get_admins():
    try:
        cur.execute("SELECT user_id FROM admin")
        rows = cur.fetchall()
        admins = []
        for row in rows:
            if await is_main_admin(row[0]):
                continue
            admins.append(row[0])
        return admins
    except Exception as e:
        print(f"Ошибка получения администраторов: {e}")

        
async def get_doctors():
    try:
        cur.execute("SELECT user_id FROM doctor")
        rows = cur.fetchall()
        doctors = []
        for row in rows:
            doctors.append(row[0])
        return doctors
    except Exception as e:
        print(f"Ошибка получения врачей: {e}")


# сеттеры
async def set_current_user_id(user_id: str, current_user_id: str):
    role = await get_role_by_id(user_id)

    try:
        if role == "patient":
            cur.execute("UPDATE patient SET current_user_id = ? WHERE user_id = ?", (current_user_id, user_id))
        elif role == "admin":
            cur.execute("UPDATE admin SET current_user_id = ? WHERE user_id = ?", (current_user_id, user_id))
        elif role == "doctor":
            cur.execute("UPDATE doctor SET current_user_id = ? WHERE user_id = ?", (current_user_id, user_id))

        db.commit()
        # print(f"Для пользователя с ID {user_id} установлен текущий пользователь с ID {current_user_id}")
    except Exception as e:
        print(f"Ошибка при установке текущего пользователя для пациента: {e}")


async def set_doctor(patient_id: str, doctor_id: str):
    try:
        cur.execute("INSERT INTO patient_doctor (patient_id, doctor_id) VALUES (?, ?)", (patient_id, doctor_id))
        db.commit()
        print(f"Пациенту с ID {patient_id} назначен доктор с ID {doctor_id}")

        current_user_for_patient = await get_current_user_id(patient_id)
        current_user_for_doctor = await get_current_user_id(doctor_id)

        if current_user_for_patient is None or current_user_for_patient == -1 or current_user_for_patient == '':
            await set_current_user_id(patient_id, doctor_id)
        if current_user_for_doctor is None or current_user_for_doctor == -1 or current_user_for_doctor == '':
            await set_current_user_id(doctor_id, patient_id)

    except Exception as e:
        print(f"Ошибка назначения врача пациенту: {e}")


async def set_message(message_id: int, chat_id: int, message_type: str, text: str, photo: str, date: str,
                      from_user: str, to_user: str, new_message: int):
    try:
        cur.execute(
            "INSERT INTO message (message_id, chat_id, type, text, photo, date, from_user, to_user, display, new_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (message_id, chat_id, message_type, text, photo, date, from_user, to_user, 1, new_message))
        db.commit()
        # print("Сообщение успешно сохранено в базе данных.")
    except Exception as e:
        print(f"Ошибка при сохранении сообщения: {e}")


async def set_display_status(message_id: int):
    try:
        cur.execute("UPDATE message SET display = 0 WHERE message_id = ?", (message_id,))
        db.commit()
        # print(f"Значение display для сообщения с ID {message_id} успешно изменено на 0.")
    except Exception as e:
        print(f"Ошибка при обновлении значения display для сообщения: {e}")


async def create_patient(user_id: str, full_name: str):
    try:
        cur.execute("INSERT INTO patient(user_id, full_name) VALUES (?, ?)",
                    (user_id, full_name))
        db.commit()
        print(f"Пациент с ID {user_id} создан успешно")
    except Exception as e:
        print(f"Ошибка создания пациента: {e}")


async def set_readability(message_id: int):
    try:
        cur.execute("UPDATE message SET new_message = 0 WHERE message_id = ?", (message_id,))
        db.commit()
        # print(f"Значение display для сообщения с ID {message_id} успешно изменено на 0.")
    except Exception as e:
        print(f"Ошибка при обновлении значения display для сообщения: {e}")


async def delete_admin_by_id(admin_id: str):
    try:
        cur.execute("DELETE FROM admin WHERE user_id = ?", (admin_id,))
        db.commit()
        print(f"Админ с ID {admin_id} успешно удален из базы данных.")
    except Exception as e:
        print(f"Ошибка при удалении админа: {e}")


async def delete_doctor_by_id(doctor_id: str):
    try:
        cur.execute("DELETE FROM doctor WHERE user_id = ?", (doctor_id,))
        db.commit()
        print(f"Врач с ID {doctor_id} успешно удален из базы данных.")
    except Exception as e:
        print(f"Ошибка при удалении врача: {e}")


async def delete_patient_doctor(doctor_id: str):
    try:
        cur.execute("DELETE FROM patient_doctor WHERE doctor_id = ?", (doctor_id,))
        db.commit()
        print(f"Записи в таблице patient_doctor для доктора с ID {doctor_id} успешно удалены.")
    except Exception as e:
        print(f"Ошибка при удалении записей в таблице patient_doctor: {e}")


# проверки
async def is_new_patient(user_id: str) -> bool:
    try:
        patient = cur.execute("SELECT * FROM patient WHERE user_id = ?", (user_id,)).fetchone()
        if patient:
            return False
        admin = cur.execute("SELECT * FROM admin WHERE user_id = ?", (user_id,)).fetchone()
        if admin:
            return False
        doctor = cur.execute("SELECT * FROM doctor WHERE user_id = ?", (user_id,)).fetchone()
        if doctor:
            return False
        return True
    except Exception as e:
        print(f"Ошибка проверки, является ли пользователь новым пациентом: {e}")

async def is_main_admin(user_id):
    try:
        cur.execute("SELECT * FROM main_admin WHERE user_id = ?", (user_id,))
        main_admin = cur.fetchone()
        return main_admin is not None
    except Exception as e:
        print(f"Ошибка при проверке главного админа: {e}")
        return False