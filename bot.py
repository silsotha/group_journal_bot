import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv
import os

load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")

# инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# состояния
class AttendanceStates(StatesGroup):
    waiting_for_date_choice = State()
    waiting_for_custom_date = State()
    waiting_for_lesson = State()
    marking_attendance = State()

class AddStudentStates(StatesGroup):
    waiting_for_name = State()

class RemoveStudentStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_full_name = State()

class EditMarkStates(StatesGroup):
    waiting_for_date_choice = State()
    waiting_for_custom_date = State()
    waiting_for_lesson = State()
    waiting_for_student = State()
    waiting_for_status = State()

class ListMarkStates(StatesGroup):
    waiting_for_date_choice = State()
    waiting_for_custom_date = State()
    waiting_for_lesson = State()

class SetHeadmanStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_full_name = State()

class SetGroupStates(StatesGroup):
    waiting_for_group_name = State()

class StatsStates(StatesGroup):
    waiting_for_choice = State()
    waiting_for_surname = State()

# инициализация базы данных
def init_db():
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                 id INTEGER PRIMARY KEY, 
                 name TEXT UNIQUE COLLATE NOCASE,
                 is_headman INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 student_id INTEGER,
                 date TEXT,
                 lesson INTEGER,
                 status TEXT,
                 FOREIGN KEY(student_id) REFERENCES students(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_info (
                 id INTEGER PRIMARY KEY CHECK (id = 1),
                 group_name TEXT)''')
    c.execute("INSERT OR IGNORE INTO group_info (id, group_name) VALUES (1, 'Не указана')")
    conn.commit()
    conn.close()

# вызов init_db() при запуске
init_db()

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.reply(
        "Привет! Я бот для ведения журнала посещаемости группы. "
        "Управляй данными легко и быстро!"
    )

# добавление студентов
@dp.message(Command("add_student"))
async def add_student_start(message: types.Message, state: FSMContext):
    await message.reply("Введи имя студента или список студентов в формате ФИО (каждый с новой строки):")
    await state.set_state(AddStudentStates.waiting_for_name)

@dp.message(AddStudentStates.waiting_for_name)
async def process_student_name(message: types.Message, state: FSMContext):
    names = message.text.strip().split('\n')
    if not names or all(not name.strip() for name in names):
        await message.reply("Список пуст. Введи хотя бы одно имя:")
        return
    
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    added = []
    skipped = []
    
    for name in names:
        name = name.strip()
        if name:
            try:
                c.execute("INSERT INTO students (name) VALUES (?)", (name,))
                added.append(name)
            except sqlite3.IntegrityError:
                skipped.append(name)
    
    conn.commit()
    conn.close()
    
    response = ""
    if added:
        response += f"Добавлены студенты: {', '.join(added)}\n"
    if skipped:
        response += f"Пропущены (уже есть): {', '.join(skipped)}"
    
    await message.reply(response or "Ничего не добавлено.")
    await state.clear()

# удаление студентов
@dp.message(Command("remove_student"))
async def remove_student_start(message: types.Message, state: FSMContext):
    await message.reply("Введи фамилию студента для удаления:")
    await state.set_state(RemoveStudentStates.waiting_for_name)

@dp.message(RemoveStudentStates.waiting_for_name)
async def process_remove_student(message: types.Message, state: FSMContext):
    surname = message.text.strip()
    if not surname:
        await message.reply("Фамилия не может быть пустой. Введи ещё раз:")
        return

    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("SELECT name FROM students ORDER BY name")
    students = [row[0] for row in c.fetchall()]
    conn.close()

    # фамилия в верхний регистр для поиска
    matching_students = [name for name in students if name.upper().startswith(surname.upper())]

    if not matching_students:
        await message.reply("Студент с такой фамилией не найден. Введи правильную фамилию:")
        return
    elif len(matching_students) > 1:
        await state.update_data(matching_students=matching_students)
        await message.reply("Найдено несколько студентов с такой фамилией. Укажи полное ФИО:\n" + "\n".join(matching_students))
        await state.set_state(RemoveStudentStates.waiting_for_full_name)
    else:
        full_name = matching_students[0]
        conn = sqlite3.connect('group_journal.db')
        c = conn.cursor()
        c.execute("DELETE FROM students WHERE name = ?", (full_name,))
        c.execute("DELETE FROM attendance WHERE student_id = (SELECT id FROM students WHERE name = ?)", (full_name,))
        conn.commit()
        conn.close()
        await message.reply(f"Студент {full_name} удалён.")
        await state.clear()

@dp.message(RemoveStudentStates.waiting_for_full_name)
async def process_remove_full_name(message: types.Message, state: FSMContext):
    full_name_input = message.text.strip()
    data = await state.get_data()
    matching_students = data.get("matching_students", [])

    if full_name_input not in matching_students:
        await message.reply("ФИО не найдено. Попробуй ещё раз:")
        return

    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("DELETE FROM students WHERE name = ?", (full_name_input,))
    c.execute("DELETE FROM attendance WHERE student_id = (SELECT id FROM students WHERE name = ?)", (full_name_input,))
    conn.commit()
    conn.close()

    await message.reply(f"Студент {full_name_input} удалён.")
    await state.clear()

@dp.message(RemoveStudentStates.waiting_for_full_name)
async def process_remove_full_name(message: types.Message, state: FSMContext):
    full_name_input = message.text.strip()

    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("SELECT id FROM students WHERE name COLLATE NOCASE = ?", (full_name_input,))
    student = c.fetchone()
    
    if not student:
        await message.reply("Ошибка: студент не найден. Попробуй ещё раз:")
        conn.close()
        return
    
    student_id = student[0]
    c.execute("DELETE FROM students WHERE id = ?", (student_id,))
    c.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    conn.commit()
    conn.close()
    
    await message.reply(f"Студент {full_name_input} удалён.")
    await state.clear()

# вывод списка студентов группы
@dp.message(Command("list_students"))
async def list_students(message: types.Message):
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("SELECT group_name FROM group_info WHERE id = 1")
    group_name = c.fetchone()[0]
    c.execute("SELECT name, is_headman FROM students ORDER BY name")
    students = c.fetchall()
    conn.close()
    if students:
        student_list = [f"{i+1}. {name}{' (📋)' if is_headman else ''}" 
                        for i, (name, is_headman) in enumerate(students)]
        student_list_text = "\n".join(student_list)
        await message.reply(f"Группа: {group_name}\nСписок студентов:\n{student_list_text}")
    else:
        await message.reply(f"Группа: {group_name}\nСписок студентов пуст.")

# отметка посещаемости
@dp.message(Command("mark"))
async def mark_attendance(message: types.Message, state: FSMContext):
    current_date = datetime.now().strftime("%d.%m.%Y")
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Сегодня ({current_date})")],
            [KeyboardButton(text="Другая дата")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.reply("Выбери дату для отметки посещаемости:", reply_markup=markup)
    await state.set_state(AttendanceStates.waiting_for_date_choice)

def get_lesson_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1⃣"), KeyboardButton(text="2⃣")],
            [KeyboardButton(text="3⃣"), KeyboardButton(text="4⃣")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

@dp.message(AttendanceStates.waiting_for_date_choice)
async def process_date_choice(message: types.Message, state: FSMContext):
    if message.text.startswith("Сегодня"):
        current_date = datetime.now().strftime("%d.%m.%Y")
        await state.update_data(date=current_date)
        await message.reply("Выбери номер пары:", reply_markup=get_lesson_keyboard())
        await state.set_state(AttendanceStates.waiting_for_lesson)
    elif message.text == "Другая дата":
        await message.reply("Введи дату в формате 'день.месяц' (например, 23.03):", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AttendanceStates.waiting_for_custom_date)
    else:
        await message.reply("Выбери одну из кнопок!")

@dp.message(AttendanceStates.waiting_for_custom_date)
async def process_custom_date(message: types.Message, state: FSMContext):
    try:
        day, month = map(int, message.text.split('.'))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError
        current_year = datetime.now().year
        date = f"{day:02d}.{month:02d}.{current_year}"
        await state.update_data(date=date)
        await message.reply("Выбери номер пары:", reply_markup=get_lesson_keyboard())
        await state.set_state(AttendanceStates.waiting_for_lesson)
    except (ValueError, IndexError):
        await message.reply("Неправильный формат. Введи дату как 'день.месяц' (например, 23.03):")

@dp.message(AttendanceStates.waiting_for_lesson)
async def process_lesson(message: types.Message, state: FSMContext):
    lesson_map = {"1⃣": 1, "2⃣": 2, "3⃣": 3, "4⃣": 4}
    if message.text not in lesson_map:
        await message.reply("Выбери номер пары с помощью кнопок!")
        return
        
    lesson = lesson_map[message.text]
    await state.update_data(lesson=lesson)
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    
    c.execute("SELECT id, name, is_headman FROM students ORDER BY name")
    all_students = c.fetchall()
    conn.close()
    
    if not all_students:
        await message.reply("Список студентов пуст. Добавь студентов через /add_student.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
    
    # отделение старосты на перекличке
    headman = None
    students = []
    for student in all_students:
        if student[2]:  # is_headman = 1
            headman = student
        else:
            students.append(student)
    
    data = await state.get_data()
    date = data['date']
    
    # указан староста --> автоматически присутствует на перекличке (подразумевается, что он = пользователь)
    if headman:
        conn = sqlite3.connect('group_journal.db')
        c = conn.cursor()
        c.execute("SELECT id FROM attendance WHERE student_id = ? AND date = ? AND lesson = ?",
                  (headman[0], date, lesson))
        attendance_record = c.fetchone()
        
        if attendance_record:
            c.execute("UPDATE attendance SET status = ? WHERE id = ?",
                      ("присутствовал", attendance_record[0]))
        else:
            c.execute("INSERT INTO attendance (student_id, date, lesson, status) VALUES (?, ?, ?, ?)",
                      (headman[0], date, lesson, "присутствовал"))
        conn.commit()
        conn.close()
    
    # если остались студенты для ручной отметки
    if students:
        await state.update_data(students=students, current_student_idx=0)
        student = students[0]
        markup = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✅"), KeyboardButton(text="❌")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.reply(f"Отметь посещаемость для {student[1]}:", reply_markup=markup)
        await state.set_state(AttendanceStates.marking_attendance)
    else:
        await message.reply("Все студенты отмечены (только староста в группе)!", reply_markup=ReplyKeyboardRemove())
        await state.clear()
    
@dp.message(AttendanceStates.marking_attendance)
async def process_mark_attendance(message: types.Message, state: FSMContext):
    status = message.text
    if status not in ["✅", "❌"]:
        await message.reply("Выбери '✅' или '❌' с кнопок.")
        return
    
    status_text = "присутствовал" if status == "✅" else "отсутствовал"
    data = await state.get_data()
    students = data['students']
    current_idx = data['current_student_idx']
    date = data['date']
    lesson = data['lesson']
    
    # каждый элемент students содержит (id, name, is_headman)
    student_id, student_name, _ = students[current_idx]  # игнор is_headman через _
    
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    # проверка на уже существующую запись
    c.execute("SELECT id FROM attendance WHERE student_id = ? AND date = ? AND lesson = ?",
              (student_id, date, lesson))
    attendance_record = c.fetchone()
    
    if attendance_record:
        c.execute("UPDATE attendance SET status = ? WHERE id = ?",
                  (status_text, attendance_record[0]))
    else:
        c.execute("INSERT INTO attendance (student_id, date, lesson, status) VALUES (?, ?, ?, ?)",
                  (student_id, date, lesson, status_text))
    conn.commit()
    conn.close()
    
    # переход к следующему студенту
    next_idx = current_idx + 1
    if next_idx < len(students):
        await state.update_data(current_student_idx=next_idx)
        next_student = students[next_idx]
        markup = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✅"), KeyboardButton(text="❌")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.reply(f"Отметь посещаемость для {next_student[1]}:", reply_markup=markup)
    else:
        await message.reply("Все студенты отмечены!", reply_markup=ReplyKeyboardRemove())
        await state.clear()

# исправление отметки
@dp.message(Command("edit_mark"))
async def edit_mark_start(message: types.Message, state: FSMContext):
    current_date = datetime.now().strftime("%d.%m.%Y")
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Сегодня ({current_date})")],
            [KeyboardButton(text="Другая дата")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.reply("Выбери дату для исправления отметки:", reply_markup=markup)
    await state.set_state(EditMarkStates.waiting_for_date_choice)

@dp.message(EditMarkStates.waiting_for_date_choice)
async def edit_process_date_choice(message: types.Message, state: FSMContext):
    if message.text.startswith("Сегодня"):
        current_date = datetime.now().strftime("%d.%m.%Y")
        await state.update_data(date=current_date)
        await message.reply("Выбери номер пары:", reply_markup=get_lesson_keyboard())
        await state.set_state(EditMarkStates.waiting_for_lesson)
    elif message.text == "Другая дата":
        await message.reply("Введи дату в формате 'день.месяц' (например, 23.03):", reply_markup=ReplyKeyboardRemove())
        await state.set_state(EditMarkStates.waiting_for_custom_date)
    else:
        await message.reply("Выбери одну из кнопок!")

@dp.message(EditMarkStates.waiting_for_custom_date)
async def edit_process_custom_date(message: types.Message, state: FSMContext):
    try:
        day, month = map(int, message.text.split('.'))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError
        current_year = datetime.now().year
        date = f"{day:02d}.{month:02d}.{current_year}"
        await state.update_data(date=date)
        await message.reply("Выбери номер пары:", reply_markup=get_lesson_keyboard())
        await state.set_state(EditMarkStates.waiting_for_lesson)
    except (ValueError, IndexError):
        await message.reply("Неправильный формат. Введи дату как 'день.месяц' (например, 23.03):")

@dp.message(EditMarkStates.waiting_for_lesson)
async def edit_process_lesson(message: types.Message, state: FSMContext):
    lesson_map = {"1⃣": 1, "2⃣": 2, "3⃣": 3, "4⃣": 4}
    if message.text not in lesson_map:
        await message.reply("Выбери номер пары с помощью кнопок!")
        return
        
    lesson = lesson_map[message.text]
    await state.update_data(lesson=lesson)
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("SELECT name FROM students ORDER BY name")
    students = c.fetchall()
    conn.close()
    
    if not students:
        await message.reply("Список студентов пуст. Добавь студентов через /add_student.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
        
    student_list = [student[0] for student in students]
    await state.update_data(student_list=student_list)
    await message.reply("Введи фамилию студента, чью отметку нужно исправить:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(EditMarkStates.waiting_for_student)

@dp.message(EditMarkStates.waiting_for_student)
async def edit_process_student(message: types.Message, state: FSMContext):
    surname = message.text.strip()
    data = await state.get_data()
    student_list = data.get('student_list')
    
    if not student_list:
        await message.reply("Ошибка: список студентов не найден. Попробуй начать заново.")
        await state.clear()
        return
    
    # фамилия в верхний регистр для поиска
    matching_students = [name for name in student_list if name.upper().startswith(surname.upper())]
    if not matching_students:
        await message.reply("Студент с такой фамилией не найден. Введи правильную фамилию:")
        return
    elif len(matching_students) > 1:
        await message.reply("Найдено несколько студентов с такой фамилией. Укажи полное ФИО:\n" + "\n".join(matching_students))
        return
    
    student_name = matching_students[0]
    await state.update_data(student_name=student_name)
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅"), KeyboardButton(text="❌")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.reply(f"Выбери новый статус для {student_name}:", reply_markup=markup)
    await state.set_state(EditMarkStates.waiting_for_status)

@dp.message(EditMarkStates.waiting_for_status)
async def edit_process_status(message: types.Message, state: FSMContext):
    status = message.text
    if status not in ["✅", "❌"]:
        await message.reply("Выбери '✅' или '❌' с кнопок.")
        return
    
    status_text = "присутствовал" if status == "✅" else "отсутствовал"
    data = await state.get_data()
    student_name = data.get('student_name')
    date = data.get('date')
    lesson = data.get('lesson')
    
    if not all([student_name, date, lesson]):
        await message.reply("Ошибка: не все данные доступны. Попробуй начать заново.")
        await state.clear()
        return
    
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("SELECT id FROM students WHERE UPPER(name) = UPPER(?)", (student_name,))
    student = c.fetchone()
    
    if not student:
        await message.reply("Ошибка: студент не найден в базе.")
        conn.close()
        await state.clear()
        return
    
    student_id = student[0]
    c.execute("SELECT id FROM attendance WHERE student_id = ? AND date = ? AND lesson = ?",
              (student_id, date, lesson))
    attendance_record = c.fetchone()
    
    if attendance_record:
        c.execute("UPDATE attendance SET status = ? WHERE id = ?",
                  (status_text, attendance_record[0]))
        conn.commit()
        await message.reply(f"Отметка для {student_name} на {date}, пара {lesson} изменена на '{status}'.",
                            reply_markup=ReplyKeyboardRemove())
    else:
        c.execute("INSERT INTO attendance (student_id, date, lesson, status) VALUES (?, ?, ?, ?)",
                  (student_id, date, lesson, status_text))
        conn.commit()
        await message.reply(f"Отметка для {student_name} на {date}, пара {lesson} добавлена как '{status}'.",
                            reply_markup=ReplyKeyboardRemove())
    
    conn.close()
    await state.clear()

# вывод посещаемости
@dp.message(Command("list_mark"))
async def list_mark_start(message: types.Message, state: FSMContext):
    current_date = datetime.now().strftime("%d.%m.%Y")
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Сегодня ({current_date})")],
            [KeyboardButton(text="Другая дата")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.reply("Выбери дату для просмотра посещаемости:", reply_markup=markup)
    await state.set_state(ListMarkStates.waiting_for_date_choice)

@dp.message(ListMarkStates.waiting_for_date_choice)
async def list_process_date_choice(message: types.Message, state: FSMContext):
    if message.text.startswith("Сегодня"):
        current_date = datetime.now().strftime("%d.%m.%Y")
        await state.update_data(date=current_date)
        await message.reply("Выбери номер пары:", reply_markup=get_lesson_keyboard())
        await state.set_state(ListMarkStates.waiting_for_lesson)
    elif message.text == "Другая дата":
        await message.reply("Введи дату в формате день.месяц (например, 23.03):", reply_markup=ReplyKeyboardRemove())
        await state.set_state(ListMarkStates.waiting_for_custom_date)
    else:
        await message.reply("Выбери одну из кнопок!")

@dp.message(ListMarkStates.waiting_for_custom_date)
async def list_process_custom_date(message: types.Message, state: FSMContext):
    try:
        day, month = map(int, message.text.split('.'))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError
        current_year = datetime.now().year
        date = f"{day:02d}.{month:02d}.{current_year}"
        await state.update_data(date=date)
        await message.reply("Выбери номер пары:", reply_markup=get_lesson_keyboard())
        await state.set_state(ListMarkStates.waiting_for_lesson)
    except (ValueError, IndexError):
        await message.reply("Неправильный формат. Введи дату как 23.03 (день.месяц).")

@dp.message(ListMarkStates.waiting_for_lesson)
async def list_process_lesson(message: types.Message, state: FSMContext):
    lesson_map = {"1⃣": 1, "2⃣": 2, "3⃣": 3, "4⃣": 4}
    if message.text not in lesson_map:
        await message.reply("Выбери номер пары с помощью кнопок!")
        return
        
    lesson = lesson_map[message.text]
    data = await state.get_data()
    date = data.get('date')
    
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("""
        SELECT s.name, a.status, s.is_headman 
        FROM students s 
        LEFT JOIN attendance a ON s.id = a.student_id 
        AND a.date = ? AND a.lesson = ? 
        ORDER BY s.name
    """, (date, lesson))
    attendance_data = c.fetchall()
    conn.close()
    
    if not attendance_data:
        await message.reply(f"Нет данных о посещаемости за {date}, пара {lesson}.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
    
    attendance_list = [
        f"{i+1}. {name}{' (📋)' if is_headman else ''}: {status if status else '❓'}"
        .replace('присутствовал', '✅')
        .replace('отсутствовал', '❌')
        for i, (name, status, is_headman) in enumerate(attendance_data)
    ]
    response = f"Посещаемость за {date}, пара {lesson}:\n" + "\n".join(attendance_list)
    await message.reply(response, reply_markup=ReplyKeyboardRemove())
    await state.clear()

# назначение старосты
@dp.message(Command("set_headman"))
async def set_headman_start(message: types.Message, state: FSMContext):
    await message.reply("Введи фамилию студента, которого хочешь назначить старостой:")
    await state.set_state(SetHeadmanStates.waiting_for_name)

@dp.message(SetHeadmanStates.waiting_for_name)
async def process_set_headman(message: types.Message, state: FSMContext):
    surname = message.text.strip()
    if not surname:
        await message.reply("Фамилия не может быть пустой. Введи ещё раз:")
        return

    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("SELECT name, is_headman FROM students ORDER BY name")
    students = c.fetchall()
    conn.close()

    # фамилия в верхний регистр для поиска
    matching_students = [student for student in students if student[0].upper().startswith(surname.upper())]

    if not matching_students:
        await message.reply("Студент с такой фамилией не найден. Введи правильную фамилию:")
        return
    elif len(matching_students) > 1:
        await state.update_data(matching_students=matching_students)
        await message.reply("Найдено несколько студентов с такой фамилией. Укажи полное ФИО:\n" + "\n".join([s[0] for s in matching_students]))
        await state.set_state(SetHeadmanStates.waiting_for_full_name)
    else:
        full_name, is_headman = matching_students[0]
        if is_headman:
            await message.reply(f"{full_name} уже является старостой!")
            await state.clear()
        else:
            conn = sqlite3.connect('group_journal.db')
            c = conn.cursor()
            c.execute("UPDATE students SET is_headman = 0 WHERE is_headman = 1")
            c.execute("UPDATE students SET is_headman = 1 WHERE name = ?", (full_name,))
            conn.commit()
            conn.close()
            await message.reply(f"{full_name} теперь староста! Он(а) будет отмечен(а) в списке.")
            await state.clear()

@dp.message(SetHeadmanStates.waiting_for_full_name)
async def process_set_headman_full_name(message: types.Message, state: FSMContext):
    full_name_input = message.text.strip()
    data = await state.get_data()
    matching_students = data.get("matching_students", [])

    if full_name_input not in matching_students:
        await message.reply("ФИО не найдено. Попробуй ещё раз:")
        return

    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("UPDATE students SET is_headman = 0 WHERE is_headman = 1")
    c.execute("UPDATE students SET is_headman = 1 WHERE name = ?", (full_name_input,))
    conn.commit()
    conn.close()

    await message.reply(f"{full_name_input} теперь староста! Он(а) будет отмечен(а) в списке.")
    await state.clear()

# установка названия группы
@dp.message(Command("set_group"))
async def set_group_start(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("SELECT group_name FROM group_info WHERE id = 1")
    current_group_name = c.fetchone()[0]
    conn.close()

    if current_group_name != 'Не указана':
        # если название группы уже установлено
        markup = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Изменить")],
                [KeyboardButton(text="Оставить")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.reply(
            f"Текущее название группы: {current_group_name}\n"
            "Хочешь изменить или оставить как есть?",
            reply_markup=markup
        )
        await state.set_state(SetGroupStates.waiting_for_group_name)
    else:
        # если название ещё не установлено, сразу запрашиваем
        await message.reply("Введи название учебной группы:")
        await state.set_state(SetGroupStates.waiting_for_group_name)

@dp.message(SetGroupStates.waiting_for_group_name)
async def process_group_name(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("SELECT group_name FROM group_info WHERE id = 1")
    current_group_name = c.fetchone()[0]
    conn.close()

    user_input = message.text.strip()

    if current_group_name != 'Не указана' and user_input in ["Изменить", "Оставить"]:
        if user_input == "Оставить":
            await message.reply(f"Название группы остаётся: {current_group_name}", reply_markup=ReplyKeyboardRemove())
            await state.clear()
        elif user_input == "Изменить":
            await message.reply("Введи новое название учебной группы:", reply_markup=ReplyKeyboardRemove())
        return

    if not user_input:
        await message.reply("Название группы не может быть пустым. Введи ещё раз:")
        return
    
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("UPDATE group_info SET group_name = ? WHERE id = 1", (user_input,))
    conn.commit()
    conn.close()
    
    await message.reply(f"Название группы установлено: {user_input}", reply_markup=ReplyKeyboardRemove())
    await state.clear()

# вывод статистики студентов
@dp.message(Command("stats"))
async def show_attendance_stats(message: types.Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Общая статистика")],
            [KeyboardButton(text="Конкретный студент")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.reply("Выбери тип статистики:", reply_markup=markup)
    await state.set_state(StatsStates.waiting_for_choice)

@dp.message(StatsStates.waiting_for_choice)
async def process_stats_choice(message: types.Message, state: FSMContext):
    if message.text == "Общая статистика":
        conn = sqlite3.connect('group_journal.db')
        c = conn.cursor()
        
        # название группы
        c.execute("SELECT group_name FROM group_info WHERE id = 1")
        group_name = c.fetchone()[0]
        
        # все студенты
        c.execute("SELECT id, name, is_headman FROM students ORDER BY name")
        students = c.fetchall()
        
        if not students:
            await message.reply(f"Группа: {group_name}\nСписок студентов пуст. Добавь студентов через /add_student.", reply_markup=ReplyKeyboardRemove())
            conn.close()
            await state.clear()
            return
        
        # статистика посещаемости
        stats = {}
        for student_id, name, is_headman in students:
            c.execute("SELECT status FROM attendance WHERE student_id = ?", (student_id,))
            records = c.fetchall()
            total_lessons = len(records)
            present = sum(1 for record in records if record[0] == "присутствовал")
            absent = total_lessons - present
            attendance_percent = (present / total_lessons * 100) if total_lessons > 0 else 100
            stats[name] = {
                "absent": absent,
                "total": total_lessons,
                "percent": attendance_percent,
                "is_headman": is_headman
            }
        
        conn.close()
        
        if not any(stats.values()):
            await message.reply(f"Группа: {group_name}\nНет данных о посещаемости.", reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return
        
        # формирование статистики
        response = f"Статистика посещаемости группы: {group_name}\n\n"
        
        # 1. кто чаще всего пропускал
        max_absent = max((data["absent"] for data in stats.values()), default=0)
        if max_absent > 0:
            most_absent = [name for name, data in stats.items() if data["absent"] == max_absent]
            response += "Чаще всего пропускали занятия:\n"
            for name in most_absent:
                response += f"- {name}{' (📋)' if stats[name]['is_headman'] else ''}: {max_absent} пропусков\n"
        else:
            response += "Никто ещё не пропускал занятия.\n"
        
        # 2. кто не пропустил ни одного
        no_absences = [name for name, data in stats.items() if data["absent"] == 0 and data["total"] > 0]
        if no_absences:
            response += "\nНи одного пропуска:\n"
            for name in no_absences:
                response += f"- {name}{' (📋)' if stats[name]['is_headman'] else ''}\n"
        else:
            response += "\nНет студентов без пропусков (или нет данных).\n"
        
        # 3. процент посещаемости для всех
        response += "\nПроцент посещаемости:\n"
        for name, data in stats.items():
            percent = data["percent"]
            total = data["total"]
            response += f"- {name}{' (📋)' if data['is_headman'] else ''}: {percent:.1f}% ({total} занятий)\n"
        
        await message.reply(response, reply_markup=ReplyKeyboardRemove())
        await state.clear()

    elif message.text == "Конкретный студент":
        await message.reply("Введи фамилию студента:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(StatsStates.waiting_for_surname)
    else:
        await message.reply("Выбери одну из кнопок!")

@dp.message(StatsStates.waiting_for_surname)
async def process_stats_surname(message: types.Message, state: FSMContext):
    surname = message.text.strip()
    if not surname:
        await message.reply("Фамилия не может быть пустой. Введи ещё раз:")
        return

    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("SELECT group_name FROM group_info WHERE id = 1")
    group_name = c.fetchone()[0]
    c.execute("SELECT id, name, is_headman FROM students ORDER BY name")
    students = c.fetchall()
    conn.close()

    # фамилия в верхний регистр для поиска
    matching_students = [student for student in students if student[1].upper().startswith(surname.upper())]

    if not matching_students:
        await message.reply("Студент с такой фамилией не найден. Введи правильную фамилию:")
        return
    elif len(matching_students) > 1:
        await state.update_data(matching_students=[s[1] for s in matching_students])
        await message.reply("Найдено несколько студентов с такой фамилией. Укажи полное ФИО:\n" + "\n".join([s[1] for s in matching_students]))
        return
    
    student_id, full_name, is_headman = matching_students[0]
    conn = sqlite3.connect('group_journal.db')
    c = conn.cursor()
    c.execute("SELECT status FROM attendance WHERE student_id = ?", (student_id,))
    records = c.fetchall()
    conn.close()

    total_lessons = len(records)
    present = sum(1 for record in records if record[0] == "присутствовал")
    absent = total_lessons - present
    attendance_percent = (present / total_lessons * 100) if total_lessons > 0 else 100

    response = f"Статистика для {full_name}{' (📋)' if is_headman else ''} (группа: {group_name}):\n"
    response += f"Всего занятий: {total_lessons}\n"
    response += f"Присутствовал: {present}\n"
    response += f"Отсутствовал: {absent}\n"
    response += f"Процент посещаемости: {attendance_percent:.1f}%"
    
    await message.reply(response)
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())