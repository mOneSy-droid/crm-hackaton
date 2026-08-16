"""Uch tildagi matnlar. Yangi til qo'shish uchun shu yerga bo'lim qo'shing.

Matnlar SOHADAN QAT'I NAZAR bir xil: "Nomi", "Yo'nalish", "Joy" kabi umumiy
so'zlar ishlatiladi. Sohaga xos atamalar ("Taom" / "Mahsulot" / "Xizmat")
backenddagi `Industry` yozuvidan keladi — bu yerda takrorlanmaydi.
"""

from __future__ import annotations

from typing import Any

TEXTS: dict[str, dict[str, str]] = {
    "uz": {
        # --- umumiy ---
        "choose_language": "Tilni tanlang:",
        "language_saved": "Til o'zgartirildi ✅",
        "main_menu": "Asosiy menyu — nima qilamiz?",
        "back": "🔙 Orqaga",
        "skip": "⏭ O'tkazib yuborish",
        "cancel": "❌ Bekor qilish",
        "cancelled": "Bekor qilindi. /menu — asosiy menyu.",
        "unknown": "Tushunmadim. /menu tugmasini bosing.",
        "error": "Xatolik yuz berdi. Birozdan keyin urinib ko'ring.",
        "loading": "Bir soniya...",
        "welcome": (
            "Assalomu alaykum, {name}! 👋\n\n"
            "Bu bot orqali biznesingizni ro'yxatdan o'tkazasiz, "
            "sharh qoldirasiz va profilingizni boshqarasiz.\n\n"
            "Avval tilni tanlang:"
        ),
        # --- menyu ---
        "reg_industry": "Sohangizni tanlang:",
        "reg_extra_optional": "Bu savolni o'tkazib yuborishingiz mumkin.",
        "menu_register": "🏪 Biznes qo'shish",
        "menu_review": "⭐ Sharh qoldirish",
        "menu_profile": "⚙️ Profilim",
        "menu_mybot": "🤖 O'z botim",
        "menu_help": "ℹ️ Yordam",
        "menu_language": "🌐 Til",
        "menu_admin": "🛠 Admin panel",
        # --- ro'yxatdan o'tish ---
        "reg_phone": (
            "Telefon raqamingiz\n\n"
            "Quyidagi tugmani bosing. Raqamni qo'lda yozish shart emas."
        ),
        "share_contact": "📞 Kontaktni yuborish",
        "reg_phone_invalid": (
            "Raqamni faqat «📞 Kontaktni yuborish» tugmasi orqali yuboring — "
            "bu xavfsizroq."
        ),
        "reg_name": "Nomi\n\nNomini yozing:",
        "reg_name_short": "Nom juda qisqa. Kamida 2 ta belgi kiriting.",
        "reg_location": (
            "Joylashuv\n\n"
            "Quyidagi tugmani bosing va xaritadan nuqtani tanlang."
        ),
        "share_location": "📍 Lokatsiyani yuborish",
        "reg_location_invalid": "Iltimos, «📍 Lokatsiyani yuborish» tugmasidan foydalaning.",
        "reg_address": "Manzil\n\nManzilni matn bilan yozing.\nMasalan: Toshkent, Chilonzor 5",
        "reg_description": "Tavsif\n\nQisqacha yozing (1-2 gap):",
        "reg_hours": "Ish vaqti\n\nQuyidagi ko'rinishda yozing: 09:00-23:00",
        "reg_hours_invalid": "Ish vaqti 09:00-23:00 ko'rinishida bo'lishi kerak. Qayta yozing:",
        "invalid_number": "Bu yerga faqat raqam yozing.",
        "reg_category": "Yo'nalish\n\nQuyidagidan birini tanlang:",
        "reg_logo": "Logotip yoki rasm yuboring.\n\nKerak bo'lmasa «O'tkazib yuborish» ni bosing.",
        "reg_confirm": "Ma'lumotlar to'g'rimi?\n\n{summary}",
        "confirm": "✅ Tasdiqlash",
        "retry": "🔁 Qaytadan",
        "reg_sending": "Yuborilyapti...",
        "reg_success": (
            "🎉 Tabriklaymiz! «{name}» ro'yxatdan o'tdi.\n\n"
            "Saytga kirish ma'lumotlaringiz:\n"
            "Login: <code>{login}</code>\n"
            "Parol: <code>{password}</code>\n\n"
            "⚠️ Parol faqat shu xabarda ko'rsatiladi — saqlab qo'ying."
        ),
        "reg_exists": "«{name}» allaqachon ro'yxatdan o'tgan. Kabinetingizga kiring:",
        "open_portal": "🔐 Saytga kirish",
        # --- sharh ---
        "rev_search": "Qaysi joyga sharh qoldirasiz?\n\nNomini yozing yoki ro'yxatdan tanlang:",
        "rev_not_found": "Bunday joy topilmadi. Boshqa nom bilan qidirib ko'ring:",
        "rev_empty": "Hozircha ro'yxatda hech narsa yo'q.",
        "rev_rate": "«{name}»\n\nBahoingizni tanlang:",
        "rev_comment": "Fikringizni yozing:",
        "rev_photo": "Rasm qo'shasizmi?\n\nKerak bo'lmasa «O'tkazib yuborish» ni bosing.",
        "rev_sent": (
            "Rahmat! Sharhingiz qabul qilindi ⭐\n\n"
            "Joy: {restaurant}\nBaho: {rating}/5"
        ),
        # --- profil ---
        "prof_none": "Sizda hali ro'yxatdan o'tgan biznes yo'q.\n\n/register — qo'shish uchun.",
        "prof_pick": "Qaysi biznesni tahrirlaymiz?",
        "prof_card": (
            "🏪 <b>{name}</b>\n"
            "⭐ Reyting: {rating} ({count} ta sharh)\n"
            "📍 {address}\n"
            "🕒 {hours}\n"
            "📝 {description}\n\n"
            "Nimani o'zgartiramiz?"
        ),
        "prof_field_name": "✏️ Nom",
        "prof_field_address": "📍 Manzil",
        "prof_field_hours": "🕒 Ish vaqti",
        "prof_field_description": "📝 Tavsif",
        "prof_field_phone": "📞 Telefon",
        "prof_field_logo": "🖼 Logotip",
        "prof_enter": "Yangi qiymatni kiriting:\n\nJoriy: {current}",
        "prof_enter_logo": "Yangi rasmni yuboring:",
        "prof_saved": "✅ Saqlandi.",
        # --- BotBuilder ---
        "bb_intro": (
            "🤖 O'zingizga shaxsiy Telegram bot yasaymiz.\n\n"
            "4 ta savolga javob bering — bot logikasi avtomatik tayyorlanadi."
        ),
        "bb_need_restaurant": "Avval biznes qo'shing: /register",
        "bb_purpose": "1/4 — Bot nima uchun kerak?\n\nMasalan: buyurtma qabul qilish, menyu ko'rsatish",
        "bb_languages": "2/4 — Bot qaysi tillarda ishlasin?\n\nTanlab bo'lgach «Davom etish» ni bosing.",
        "bb_features": "3/4 — Qanday funksiyalar kerak?\n\nVergul bilan yozing.\nMasalan: menyu, bron qilish, aksiyalar",
        "bb_tone": "4/4 — Muloqot uslubi qanday bo'lsin?\n\nMasalan: do'stona, rasmiy, qisqa",
        "bb_generating": "Bot logikasi tayyorlanyapti... ⏳",
        "bb_ready": (
            "✅ Bot logikasi tayyor!\n\n"
            "Endi @BotFather ga o'ting:\n"
            "1. /newbot buyrug'ini yuboring\n"
            "2. Bot nomi va username tanlang\n"
            "3. BotFather bergan tokenni shu yerga tashlang\n\n"
            "🔒 Token shifrlanadi va xabaringiz darhol o'chiriladi."
        ),
        "bb_token_invalid": "Token noto'g'ri formatda. @BotFather bergan tokenni to'liq yuboring.",
        "bb_token_ok": "🎉 «@{username}» boti ulandi va ishga tushdi!",
        "bb_status": "🤖 Botingiz: @{username}\nHolat: {status}",
        "bb_continue": "➡️ Davom etish",
        # --- yordam ---
        "help": (
            "<b>Buyruqlar</b>\n\n"
            "/start — boshlash\n"
            "/menu — asosiy menyu\n"
            "/register — biznes qo'shish\n"
            "/review — sharh qoldirish\n"
            "/profile — profilni tahrirlash\n"
            "/mybot — o'z botingizni yasash\n"
            "/language — tilni o'zgartirish\n"
            "/cancel — jarayonni bekor qilish\n\n"
            "Savol bo'lsa: @{support}"
        ),
        # --- admin ---
        "admin_denied": "Bu bo'lim faqat adminlar uchun.",
        "admin_menu": "🛠 Admin panel",
        "admin_stats": "📊 Statistika",
        "admin_restaurants": "🏪 Bizneslar",
        "admin_add_admin": "👤 Admin qo'shish",
        "admin_remove_admin": "🚫 Adminni olib tashlash",
        "admin_ask_id": "Telegram user ID raqamini kiriting:",
        "admin_bad_id": "ID faqat raqamlardan iborat bo'lishi kerak.",
        "admin_added": "✅ Admin qo'shildi: {id}",
        "admin_removed": "✅ Admin olib tashlandi: {id}",
        "admin_cant_remove_super": "Bu admin sozlamalarda qat'iy belgilangan — bot ichidan olib bo'lmaydi.",
        "admin_stats_text": "📊 Jami bizneslar: {restaurants}\n👤 Adminlar: {admins}",
        # --- bildirishnomalar ---
        "notify_new_review": (
            "⭐ «{restaurant_name}» ga yangi sharh!\n\n"
            "Baho: {rating}/5\n{text}"
        ),
        "notify_owner_reply": "💬 «{restaurant_name}» sizning sharhingizga javob berdi:\n\n{reply}",
        "notify_review_approved": "✅ Sharhingiz tasdiqlandi.",
        "notify_review_rejected": "❌ Sharhingiz moderatsiyadan o'tmadi.",
        "notify_bot_status": "🤖 @{bot_username} boti holati: {status}",
        "notify_tenant_lead": (
            "📨 «{restaurant_name}» botiga yangi so'rov!\n\n"
            "Turi: {flow_label}\n"
            "Mijoz: {customer_name}\n\n{answers}"
        ),
    },
    "ru": {
        "choose_language": "Выберите язык:",
        "language_saved": "Язык изменён ✅",
        "main_menu": "Главное меню — что делаем?",
        "back": "🔙 Назад",
        "skip": "⏭ Пропустить",
        "cancel": "❌ Отменить",
        "cancelled": "Отменено. /menu — главное меню.",
        "unknown": "Не понял. Нажмите /menu.",
        "error": "Произошла ошибка. Попробуйте чуть позже.",
        "loading": "Секунду...",
        "welcome": (
            "Здравствуйте, {name}! 👋\n\n"
            "Через этот бот вы зарегистрируете свой бизнес, оставите отзыв "
            "и будете управлять профилем.\n\n"
            "Сначала выберите язык:"
        ),
        "reg_industry": "Выберите вашу сферу:",
        "reg_extra_optional": "Этот вопрос можно пропустить.",
        "menu_register": "🏪 Добавить бизнес",
        "menu_review": "⭐ Оставить отзыв",
        "menu_profile": "⚙️ Мой профиль",
        "menu_mybot": "🤖 Мой бот",
        "menu_help": "ℹ️ Помощь",
        "menu_language": "🌐 Язык",
        "menu_admin": "🛠 Админ-панель",
        "reg_phone": (
            "Ваш номер телефона\n\n"
            "Нажмите кнопку ниже. Вводить вручную не нужно."
        ),
        "share_contact": "📞 Отправить контакт",
        "reg_phone_invalid": (
            "Отправьте номер только через кнопку «📞 Отправить контакт» — так безопаснее."
        ),
        "reg_name": "Название\n\nНапишите название:",
        "reg_name_short": "Слишком короткое название. Минимум 2 символа.",
        "reg_location": (
            "Местоположение\n\nНажмите кнопку и выберите точку на карте."
        ),
        "share_location": "📍 Отправить местоположение",
        "reg_location_invalid": "Пожалуйста, используйте кнопку «📍 Отправить местоположение».",
        "reg_address": "Адрес\n\nНапишите адрес текстом.\nНапример: Ташкент, Чиланзар 5",
        "reg_description": "Описание\n\nКоротко о себе (1-2 предложения):",
        "reg_hours": "Часы работы\n\nВ таком виде: 09:00-23:00",
        "reg_hours_invalid": "Часы работы должны быть в виде 09:00-23:00. Напишите ещё раз:",
        "invalid_number": "Здесь нужно указать только число.",
        "reg_category": "Направление\n\nВыберите один вариант:",
        "reg_logo": "Отправьте логотип или фото.\n\nЕсли не нужно — нажмите «Пропустить».",
        "reg_confirm": "Всё верно?\n\n{summary}",
        "confirm": "✅ Подтвердить",
        "retry": "🔁 Заново",
        "reg_sending": "Отправляем...",
        "reg_success": (
            "🎉 Поздравляем! «{name}» зарегистрирован.\n\n"
            "Данные для входа на сайт:\n"
            "Логин: <code>{login}</code>\n"
            "Пароль: <code>{password}</code>\n\n"
            "⚠️ Пароль показывается только в этом сообщении — сохраните его."
        ),
        "reg_exists": "«{name}» уже зарегистрирован. Войдите в кабинет:",
        "open_portal": "🔐 Войти на сайт",
        "rev_search": "На какое заведение оставите отзыв?\n\nНапишите название или выберите из списка:",
        "rev_not_found": "Заведение не найдено. Попробуйте другое название:",
        "rev_empty": "Пока список пуст.",
        "rev_rate": "«{name}»\n\nВыберите оценку:",
        "rev_comment": "Напишите ваш отзыв:",
        "rev_photo": "Добавите фото?\n\nЕсли нет — нажмите «Пропустить».",
        "rev_sent": (
            "Спасибо! Отзыв принят ⭐\n\nЗаведение: {restaurant}\nОценка: {rating}/5"
        ),
        "prof_none": "У вас пока нет зарегистрированного бизнеса.\n\n/register — добавить.",
        "prof_pick": "Какой бизнес редактируем?",
        "prof_card": (
            "🏪 <b>{name}</b>\n"
            "⭐ Рейтинг: {rating} ({count} отзывов)\n"
            "📍 {address}\n"
            "🕒 {hours}\n"
            "📝 {description}\n\n"
            "Что изменим?"
        ),
        "prof_field_name": "✏️ Название",
        "prof_field_address": "📍 Адрес",
        "prof_field_hours": "🕒 Часы работы",
        "prof_field_description": "📝 Описание",
        "prof_field_phone": "📞 Телефон",
        "prof_field_logo": "🖼 Логотип",
        "prof_enter": "Введите новое значение:\n\nСейчас: {current}",
        "prof_enter_logo": "Отправьте новое фото:",
        "prof_saved": "✅ Сохранено.",
        "bb_intro": (
            "🤖 Создадим вам личного Telegram-бота.\n\n"
            "Ответьте на 4 вопроса — логика бота подготовится автоматически."
        ),
        "bb_need_restaurant": "Сначала добавьте бизнес: /register",
        "bb_purpose": "1/4 — Для чего нужен бот?\n\nНапример: приём заказов, показ меню",
        "bb_languages": "2/4 — На каких языках работает бот?\n\nПосле выбора нажмите «Продолжить».",
        "bb_features": "3/4 — Какие функции нужны?\n\nЧерез запятую.\nНапример: меню, бронирование, акции",
        "bb_tone": "4/4 — Какой стиль общения?\n\nНапример: дружелюбный, официальный, краткий",
        "bb_generating": "Готовим логику бота... ⏳",
        "bb_ready": (
            "✅ Логика бота готова!\n\n"
            "Теперь перейдите к @BotFather:\n"
            "1. Отправьте /newbot\n"
            "2. Выберите имя и username\n"
            "3. Пришлите сюда токен от BotFather\n\n"
            "🔒 Токен будет зашифрован, а ваше сообщение сразу удалено."
        ),
        "bb_token_invalid": "Неверный формат токена. Пришлите токен от @BotFather полностью.",
        "bb_token_ok": "🎉 Бот «@{username}» подключён и запущен!",
        "bb_status": "🤖 Ваш бот: @{username}\nСтатус: {status}",
        "bb_continue": "➡️ Продолжить",
        "help": (
            "<b>Команды</b>\n\n"
            "/start — начать\n"
            "/menu — главное меню\n"
            "/register — добавить бизнес\n"
            "/review — оставить отзыв\n"
            "/profile — редактировать профиль\n"
            "/mybot — создать своего бота\n"
            "/language — сменить язык\n"
            "/cancel — отменить процесс\n\n"
            "Вопросы: @{support}"
        ),
        "admin_denied": "Этот раздел только для администраторов.",
        "admin_menu": "🛠 Админ-панель",
        "admin_stats": "📊 Статистика",
        "admin_restaurants": "🏪 Бизнесы",
        "admin_add_admin": "👤 Добавить админа",
        "admin_remove_admin": "🚫 Удалить админа",
        "admin_ask_id": "Введите Telegram user ID:",
        "admin_bad_id": "ID должен состоять только из цифр.",
        "admin_added": "✅ Админ добавлен: {id}",
        "admin_removed": "✅ Админ удалён: {id}",
        "admin_cant_remove_super": "Этот админ задан в настройках — его нельзя удалить из бота.",
        "admin_stats_text": "📊 Всего бизнесов: {restaurants}\n👤 Админов: {admins}",
        "notify_new_review": (
            "⭐ Новый отзыв на «{restaurant_name}»!\n\nОценка: {rating}/5\n{text}"
        ),
        "notify_owner_reply": "💬 «{restaurant_name}» ответил на ваш отзыв:\n\n{reply}",
        "notify_review_approved": "✅ Ваш отзыв одобрен.",
        "notify_review_rejected": "❌ Ваш отзыв не прошёл модерацию.",
        "notify_bot_status": "🤖 Статус бота @{bot_username}: {status}",
        "notify_tenant_lead": (
            "📨 Новая заявка в боте «{restaurant_name}»!\n\n"
            "Тип: {flow_label}\n"
            "Клиент: {customer_name}\n\n{answers}"
        ),
    },
    "en": {
        "choose_language": "Choose a language:",
        "language_saved": "Language changed ✅",
        "main_menu": "Main menu — what shall we do?",
        "back": "🔙 Back",
        "skip": "⏭ Skip",
        "cancel": "❌ Cancel",
        "cancelled": "Cancelled. /menu — main menu.",
        "unknown": "I didn't get that. Press /menu.",
        "error": "Something went wrong. Please try again shortly.",
        "loading": "One moment...",
        "welcome": (
            "Hello, {name}! 👋\n\n"
            "Use this bot to register your business, leave reviews "
            "and manage your profile.\n\n"
            "First, choose a language:"
        ),
        "reg_industry": "Choose your industry:",
        "reg_extra_optional": "You can skip this question.",
        "menu_register": "🏪 Add a business",
        "menu_review": "⭐ Leave a review",
        "menu_profile": "⚙️ My profile",
        "menu_mybot": "🤖 My bot",
        "menu_help": "ℹ️ Help",
        "menu_language": "🌐 Language",
        "menu_admin": "🛠 Admin panel",
        "reg_phone": (
            "Your phone number\n\nTap the button below. No need to type it."
        ),
        "share_contact": "📞 Share contact",
        "reg_phone_invalid": "Please use the «📞 Share contact» button — it's safer.",
        "reg_name": "Name\n\nType the name:",
        "reg_name_short": "That name is too short. At least 2 characters.",
        "reg_location": "Location\n\nTap the button and pick the spot on the map.",
        "share_location": "📍 Share location",
        "reg_location_invalid": "Please use the «📍 Share location» button.",
        "reg_address": "Address\n\nWrite the address as text.\nExample: Tashkent, Chilanzar 5",
        "reg_description": "Description\n\nA sentence or two about your business:",
        "reg_hours": "Working hours\n\nIn this format: 09:00-23:00",
        "reg_hours_invalid": "Working hours must look like 09:00-23:00. Try again:",
        "invalid_number": "Please enter digits only here.",
        "reg_category": "Category\n\nPick one:",
        "reg_logo": "Send a logo or photo.\n\nNot needed? Tap «Skip».",
        "reg_confirm": "Is everything correct?\n\n{summary}",
        "confirm": "✅ Confirm",
        "retry": "🔁 Start over",
        "reg_sending": "Sending...",
        "reg_success": (
            "🎉 Congratulations! «{name}» is registered.\n\n"
            "Your website credentials:\n"
            "Login: <code>{login}</code>\n"
            "Password: <code>{password}</code>\n\n"
            "⚠️ The password is shown only in this message — save it."
        ),
        "reg_exists": "«{name}» is already registered. Sign in to your dashboard:",
        "open_portal": "🔐 Open dashboard",
        "rev_search": "Which place are you reviewing?\n\nType a name or pick from the list:",
        "rev_not_found": "Nothing found. Try a different name:",
        "rev_empty": "Nothing listed yet.",
        "rev_rate": "«{name}»\n\nChoose your rating:",
        "rev_comment": "Write your review:",
        "rev_photo": "Add a photo?\n\nIf not, tap «Skip».",
        "rev_sent": "Thank you! Your review was received ⭐\n\nPlace: {restaurant}\nRating: {rating}/5",
        "prof_none": "You have no registered business yet.\n\n/register — add one.",
        "prof_pick": "Which business are we editing?",
        "prof_card": (
            "🏪 <b>{name}</b>\n"
            "⭐ Rating: {rating} ({count} reviews)\n"
            "📍 {address}\n"
            "🕒 {hours}\n"
            "📝 {description}\n\n"
            "What shall we change?"
        ),
        "prof_field_name": "✏️ Name",
        "prof_field_address": "📍 Address",
        "prof_field_hours": "🕒 Working hours",
        "prof_field_description": "📝 Description",
        "prof_field_phone": "📞 Phone",
        "prof_field_logo": "🖼 Logo",
        "prof_enter": "Enter the new value:\n\nCurrent: {current}",
        "prof_enter_logo": "Send the new photo:",
        "prof_saved": "✅ Saved.",
        "bb_intro": (
            "🤖 Let's build your own Telegram bot.\n\n"
            "Answer 4 questions — the bot logic is prepared automatically."
        ),
        "bb_need_restaurant": "Add a business first: /register",
        "bb_purpose": "1/4 — What is the bot for?\n\nExample: taking orders, showing the menu",
        "bb_languages": "2/4 — Which languages should it speak?\n\nTap «Continue» when done.",
        "bb_features": "3/4 — Which features do you need?\n\nComma-separated.\nExample: menu, booking, promos",
        "bb_tone": "4/4 — What tone of voice?\n\nExample: friendly, formal, brief",
        "bb_generating": "Preparing the bot logic... ⏳",
        "bb_ready": (
            "✅ Bot logic is ready!\n\n"
            "Now go to @BotFather:\n"
            "1. Send /newbot\n"
            "2. Pick a name and username\n"
            "3. Paste the token BotFather gives you here\n\n"
            "🔒 The token is encrypted and your message is deleted immediately."
        ),
        "bb_token_invalid": "That token format is wrong. Send the full token from @BotFather.",
        "bb_token_ok": "🎉 Bot «@{username}» is connected and running!",
        "bb_status": "🤖 Your bot: @{username}\nStatus: {status}",
        "bb_continue": "➡️ Continue",
        "help": (
            "<b>Commands</b>\n\n"
            "/start — get started\n"
            "/menu — main menu\n"
            "/register — add a business\n"
            "/review — leave a review\n"
            "/profile — edit your profile\n"
            "/mybot — build your own bot\n"
            "/language — change language\n"
            "/cancel — cancel the current step\n\n"
            "Questions: @{support}"
        ),
        "admin_denied": "This section is for admins only.",
        "admin_menu": "🛠 Admin panel",
        "admin_stats": "📊 Statistics",
        "admin_restaurants": "🏪 Businesses",
        "admin_add_admin": "👤 Add admin",
        "admin_remove_admin": "🚫 Remove admin",
        "admin_ask_id": "Enter the Telegram user ID:",
        "admin_bad_id": "The ID must contain digits only.",
        "admin_added": "✅ Admin added: {id}",
        "admin_removed": "✅ Admin removed: {id}",
        "admin_cant_remove_super": "This admin is pinned in the settings and cannot be removed from the bot.",
        "admin_stats_text": "📊 Businesses: {restaurants}\n👤 Admins: {admins}",
        "notify_new_review": "⭐ New review for «{restaurant_name}»!\n\nRating: {rating}/5\n{text}",
        "notify_owner_reply": "💬 «{restaurant_name}» replied to your review:\n\n{reply}",
        "notify_review_approved": "✅ Your review was approved.",
        "notify_review_rejected": "❌ Your review did not pass moderation.",
        "notify_bot_status": "🤖 Bot @{bot_username} status: {status}",
        "notify_tenant_lead": (
            "📨 New request in the «{restaurant_name}» bot!\n\n"
            "Type: {flow_label}\n"
            "Customer: {customer_name}\n\n{answers}"
        ),
    },
}

LANGUAGE_NAMES = {"uz": "🇺🇿 O'zbek", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

#: "Bekor qilish" tugmasi matni har uch tilda — reply-klaviatura tugmasi
#: oddiy matn sifatida keladi, shuning uchun uni alohida ushlash kerak.
CANCEL_TEXTS = frozenset(TEXTS[code]["cancel"] for code in TEXTS)

SUPPORT_USERNAME = "bidora_support"


def t(lang: str, key: str, **kwargs: Any) -> str:
    """Tarjimani oladi. Kalit topilmasa o'zbekchaga, u ham bo'lmasa kalitning o'ziga tushadi."""
    table = TEXTS.get(lang) or TEXTS["uz"]
    text = table.get(key) or TEXTS["uz"].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            # Shablon va argumentlar mos kelmasa — xom matnni qaytaramiz,
            # bot yiqilgandan ko'ra shu yaxshi
            return text
    return text
