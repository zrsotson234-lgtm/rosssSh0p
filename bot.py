import asyncio
import sqlite3
import os
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

TOKEN = os.getenv("TOKEN", "BOT_TOKEN")

GROUP_ID = int(os.getenv("GROUP_ID", "-1003938436395"))

bot = Bot(TOKEN)
dp = Dispatcher()

# ================= DB =================

db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,
    items TEXT,
    server TEXT,
    price INTEGER,
    login TEXT,
    password TEXT,
    status TEXT DEFAULT 'available'
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    account_id INTEGER,
    status TEXT DEFAULT 'pending'
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    text TEXT,
    status TEXT DEFAULT 'open'
)
""")

db.commit()

# ================= STATES =================

ticket_state: dict[int, object] = {}
admin_reply_state: dict[int, bool] = {}
admin_ticket_map: dict[int, int] = {}
add_state: dict[int, dict] = {}
delete_state: dict[int, bool] = {}

# ================= HELPERS =================

def user_label(user: types.User) -> str:
    return f"@{user.username}" if user.username else f"id:{user.id}"

def is_admin_chat(chat_id: int) -> bool:
    return chat_id == GROUP_ID

# ================= KEYBOARDS =================

def user_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Магазин аккаунтов", callback_data="shop")],
        [InlineKeyboardButton(text="💼 Продать аккаунт", callback_data="sell")],
        [InlineKeyboardButton(text="💰 Купить валюту", callback_data="buy_money")],
        [InlineKeyboardButton(text="💸 Продать валюту", callback_data="sell_money")],
        [InlineKeyboardButton(text="🏠 Недвижимость", callback_data="property")],
        [InlineKeyboardButton(text="⭐ Отзывы", callback_data="review")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
    ])

def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Тикеты", callback_data="tickets_list")],
        [InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="add_acc")],
        [InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data="del_acc")],
    ])

def pay_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Я оплатил", callback_data=f"paid_{order_id}")]
    ])

def ticket_kb(tid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✉️ Ответить", callback_data=f"reply_{tid}"),
            InlineKeyboardButton(text="🔒 Закрыть", callback_data=f"close_{tid}"),
        ]
    ])

# ================= START =================

@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("👋 Бот запущен", reply_markup=user_kb())

@dp.message(Command("panel"))
async def panel(m: types.Message):
    if not is_admin_chat(m.chat.id):
        return
    await m.answer("⚙️ Админ панель", reply_markup=admin_kb())

# ================= SHOP =================

@dp.callback_query(F.data == "shop")
async def shop(c: types.CallbackQuery):
    await c.answer()

    cur.execute(
        "SELECT id, level, items, server, price FROM accounts WHERE status='available'"
    )
    rows = cur.fetchall()

    if not rows:
        return await c.message.answer("❌ Нет доступных аккаунтов")

    for a in rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Купить за {a[4]}₽", callback_data=f"buy_{a[0]}")]
        ])
        await c.message.answer(
            f"📦 АККАУНТ #{a[0]}\n"
            f"🎮 {a[1]}\n"
            f"💰 {a[2]}\n"
            f"🌍 {a[3]}\n"
            f"💵 {a[4]}₽",
            reply_markup=kb,
        )

# ================= BUY =================

@dp.callback_query(F.data.startswith("buy_") & ~F.data.startswith("buy_money"))
async def buy(c: types.CallbackQuery):
    await c.answer()

    parts = c.data.split("_")
    if len(parts) != 2 or not parts[1].isdigit():
        return

    acc_id = int(parts[1])
    u = c.from_user

    cur.execute("SELECT status FROM accounts WHERE id=?", (acc_id,))
    row = cur.fetchone()
    if not row or row[0] != "available":
        return await c.message.answer("❌ Аккаунт уже недоступен")

    cur.execute(
        "SELECT id FROM orders WHERE user_id=? AND status='pending'",
        (u.id,),
    )
    if cur.fetchone():
        return await c.message.answer("❌ У вас уже есть активный заказ")

    cur.execute(
        "INSERT INTO orders (user_id, username, account_id) VALUES (?, ?, ?)",
        (u.id, user_label(u), acc_id),
    )
    db.commit()
    order_id = cur.lastrowid

    await c.message.answer(
        f"💳 Заказ #{order_id} создан. Оплатите и нажмите кнопку ниже.2200701210959612",
        reply_markup=pay_kb(order_id),
    )

# ================= AUTO DELIVERY =================

@dp.callback_query(F.data.startswith("paid_"))
async def paid(c: types.CallbackQuery):
    await c.answer()

    order_id = int(c.data.split("_")[1])

    cur.execute("UPDATE orders SET status='paid' WHERE id=?", (order_id,))
    db.commit()

    await bot.send_message(
        GROUP_ID,
        f"💰 ПОДТВЕРЖДЕНИЕ ОПЛАТЫ\n🆔 Заказ #{order_id}\n👤 {user_label(c.from_user)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить выдачу", callback_data=f"confirm_{order_id}")]
        ]),
    )

    try:
        await c.message.edit_text("⏳ Ожидайте подтверждения администратора")
    except Exception:
        await c.message.answer("⏳ Ожидайте подтверждения администратора")

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm(c: types.CallbackQuery):
    await c.answer()

    if not is_admin_chat(c.message.chat.id):
        return await c.message.answer("⛔ Только в админ-чате")

    order_id = int(c.data.split("_")[1])

    cur.execute("SELECT user_id, account_id FROM orders WHERE id=?", (order_id,))
    row = cur.fetchone()
    if not row:
        return await c.message.answer("❌ Заказ не найден")
    user_id, acc_id = row

    cur.execute("SELECT login, password FROM accounts WHERE id=?", (acc_id,))
    acc = cur.fetchone()
    if not acc:
        return await c.message.answer("❌ Аккаунт не найден")
    login, password = acc

    cur.execute("UPDATE orders SET status='done' WHERE id=?", (order_id,))
    cur.execute("UPDATE accounts SET status='sold' WHERE id=?", (acc_id,))
    db.commit()

    try:
        await bot.send_message(
            user_id,
            f"✅ ЗАКАЗ ВЫДАН\n\n👤 Логин: {login}\n🔐 Пароль: {password}",
        )
    except Exception as e:
        log.exception("send to user failed: %s", e)
        await c.message.answer(f"⚠️ Не удалось отправить сообщение пользователю {user_id}")

    try:
        await c.message.edit_text(f"✔ Заказ #{order_id} подтверждён и выдан")
    except Exception:
        await c.message.answer(f"✔ Заказ #{order_id} подтверждён и выдан")

# ================= SIMPLE FORMS (sell / money / property / review) =================

@dp.callback_query(F.data == "sell")
async def sell(c: types.CallbackQuery):
    await c.answer()
    ticket_state[c.from_user.id] = "sell_account"
    await c.message.answer("💼 Опишите аккаунт, который хотите продать (уровень, имущество, сервер, цена):")

@dp.callback_query(F.data == "buy_money")
async def buy_money(c: types.CallbackQuery):
    await c.answer()
    ticket_state[c.from_user.id] = "buy_money"
    await c.message.answer("💰 Введите сумму покупки валюты:")

@dp.callback_query(F.data == "sell_money")
async def sell_money(c: types.CallbackQuery):
    await c.answer()
    ticket_state[c.from_user.id] = "sell_money"
    await c.message.answer("💸 Введите сумму для продажи валюты:")

@dp.callback_query(F.data == "property")
async def property_cb(c: types.CallbackQuery):
    await c.answer()
    ticket_state[c.from_user.id] = "property"
    await c.message.answer("🏠 Опишите недвижимость:")

@dp.callback_query(F.data == "review")
async def review(c: types.CallbackQuery):
    await c.answer()
    ticket_state[c.from_user.id] = "review"
    await c.message.answer("⭐ Напишите ваш отзыв:")

@dp.callback_query(F.data == "support")
async def support(c: types.CallbackQuery):
    await c.answer()
    ticket_state[c.from_user.id] = "support"
    await c.message.answer("🆘 Опишите ваш вопрос:")

# Заголовок и подпись поля для каждого типа заявки
GROUP_FORMS = {
    "sell_account": ("💼 ПРОДАЖА АККАУНТА", "📌"),
    "buy_money":    ("💰 ЗАКАЗ ВАЛЮТЫ",     "💵 Сумма:"),
    "sell_money":   ("💸 ПРОДАЖА ВАЛЮТЫ",   "💵 Сумма:"),
    "property":     ("🏠 НЕДВИЖИМОСТЬ",     "📌"),
    "review":       ("⭐ ОТЗЫВ",            "📝"),
    "support":      ("🆘 ПОДДЕРЖКА",        "📌"),
}

# ================= ROUTER =================

@dp.message()
async def router(m: types.Message):
    uid = m.from_user.id
    text = m.text or ""

    # ===== Админские состояния (работают в любом чате, в т.ч. в группе) =====
    if uid in add_state:
        s = add_state[uid]

        if "level" not in s:
            s["level"] = text
            return await m.answer("💰 Имущество:")
        if "items" not in s:
            s["items"] = text
            return await m.answer("🌍 Сервер:")
        if "server" not in s:
            s["server"] = text
            return await m.answer("💵 Цена (число):")
        if "price" not in s:
            if not text.isdigit():
                return await m.answer("❌ Введите цену числом")
            s["price"] = int(text)
            return await m.answer("👤 Логин:")
        if "login" not in s:
            s["login"] = text
            return await m.answer("🔐 Пароль:")

        s["password"] = text

        cur.execute("""
            INSERT INTO accounts (level, items, server, price, login, password)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (s["level"], s["items"], s["server"], s["price"], s["login"], s["password"]))
        db.commit()
        add_state.pop(uid, None)

        return await m.answer("✅ Аккаунт добавлен")

    if uid in delete_state:
        if not text.isdigit():
            return await m.answer("❌ ID должен быть числом")
        acc_id = int(text)
        cur.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
        db.commit()
        delete_state.pop(uid, None)
        return await m.answer(f"🗑 Удалён #{acc_id}")

    if uid in admin_reply_state:
        admin_reply_state.pop(uid, None)
        tid = admin_ticket_map.pop(uid, None)
        if tid is None:
            return
        cur.execute("SELECT user_id FROM tickets WHERE id=?", (tid,))
        row = cur.fetchone()
        if not row:
            return await m.answer("❌ Тикет не найден")
        try:
            await bot.send_message(row[0], f"📩 Ответ поддержки:\n\n{text}")
            await m.answer("✅ Отправлено")
        except Exception as e:
            log.exception("reply failed: %s", e)
            await m.answer("⚠️ Не удалось отправить ответ")
        return

    # Дальше — пользовательские состояния, только в личке
    if m.chat.type != "private":
        return
    if not text:
        return

    # ===== Любая заявка от пользователя сохраняется как тикет с кнопкой "Ответить" =====
    if uid in ticket_state:
        kind = ticket_state.pop(uid)
        title, label = GROUP_FORMS.get(str(kind), ("📩 ЗАЯВКА", "📌"))

        cur.execute(
            "INSERT INTO tickets (user_id, username, text) VALUES (?, ?, ?)",
            (uid, user_label(m.from_user), f"[{kind}] {text}"),
        )
        db.commit()
        tid = cur.lastrowid

        await bot.send_message(
            GROUP_ID,
            f"{title} #{tid}\n👤 {user_label(m.from_user)}\n{label} {text}",
            reply_markup=ticket_kb(tid),
        )
        return await m.answer(f"✅ Заявка #{tid} отправлена")

# ================= TICKETS LIST =================

@dp.callback_query(F.data == "tickets_list")
async def tickets_list(c: types.CallbackQuery):
    await c.answer()

    cur.execute(
        "SELECT id, username, text, status FROM tickets ORDER BY id DESC LIMIT 10"
    )
    rows = cur.fetchall()

    if not rows:
        return await c.message.answer("📭 Нет тикетов")

    for tid, username, text, status in rows:
        await c.message.answer(
            f"🎫 #{tid}\n👤 {username}\n📌 {text}\n📊 {status}",
            reply_markup=ticket_kb(tid),
        )

# ================= REPLY / CLOSE =================

@dp.callback_query(F.data.startswith("reply_"))
async def reply_start(c: types.CallbackQuery):
    await c.answer()
    tid = int(c.data.split("_")[1])
    admin_reply_state[c.from_user.id] = True
    admin_ticket_map[c.from_user.id] = tid
    await c.message.answer(f"✍️ Введите ответ для тикета #{tid}:")

@dp.callback_query(F.data.startswith("close_"))
async def close_ticket(c: types.CallbackQuery):
    await c.answer()
    tid = int(c.data.split("_")[1])
    cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
    db.commit()
    try:
        await c.message.edit_text(f"🔒 Тикет #{tid} закрыт")
    except Exception:
        await c.message.answer(f"🔒 Тикет #{tid} закрыт")

# ================= ADMIN ACTIONS =================

@dp.callback_query(F.data == "add_acc")
async def add_acc(c: types.CallbackQuery):
    await c.answer()
    if not is_admin_chat(c.message.chat.id):
        return await c.message.answer("⛔ Только в админ-чате")
    add_state[c.from_user.id] = {}
    await c.message.answer("🎮 Уровень:")

@dp.callback_query(F.data == "del_acc")
async def del_acc(c: types.CallbackQuery):
    await c.answer()
    if not is_admin_chat(c.message.chat.id):
        return await c.message.answer("⛔ Только в админ-чате")
    delete_state[c.from_user.id] = True
    await c.message.answer("🗑 Введите ID аккаунта:")

# ================= RUN =================

async def main():
    try:
        await dp.start_polling(bot)
    finally:
        db.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
