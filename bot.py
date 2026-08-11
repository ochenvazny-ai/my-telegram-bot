import os
import sys
import asyncio
import logging
import threading
import atexit
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters,
)

import database as db
import handlers_user as hu
import handlers_admin as ha
from config import (
    BOT_TOKEN, HW_TEXT, HW_DUE, ANN_TEXT, ANN_CONFIRM, REPLNOTE_TEXT, REPLNOTE_CONFIRM, PH_DATE,
    SCHED_UPLOAD_TEXT, SCHED_FIELD_VALUE, ADMIN_ID, ADMIN_NAME,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------- Фильтр токена из логов ----------
# httpx логирует полные URL, включая токен бота. Этот фильтр заменяет его на ***.
class TokenRedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if BOT_TOKEN and BOT_TOKEN in record.getMessage():
            record.msg = record.getMessage().replace(BOT_TOKEN, "***TOKEN***")
        return True


for name in ("httpx", "telegram", "urllib3"):
    logging.getLogger(name).addFilter(TokenRedactFilter())


async def error_handler(update, context):
    logger.error("Необработанное исключение:", exc_info=context.error)


# ---------- Health-check сервер для Railway/Render ----------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


threading.Thread(target=run_health_server, daemon=True).start()


def build_conversations():
    fallback = [
        CallbackQueryHandler(ha.cancel_conversation, pattern="^cancel_action$"),
        CallbackQueryHandler(ha.back_to_admin_panel, pattern="^admin_panel$"),
    ]

    conv_add_hw = ConversationHandler(
        entry_points=[CallbackQueryHandler(ha.add_hw_start, pattern="^a_add_hw$")],
        states={
            HW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.add_hw_text)],
            HW_DUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.add_hw_due)],
        },
        fallbacks=fallback,
    )

    conv_add_ann = ConversationHandler(
        entry_points=[CallbackQueryHandler(ha.add_ann_start, pattern="^a_add_ann$")],
        states={
            ANN_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.add_ann_text)],
            ANN_CONFIRM: [CallbackQueryHandler(ha.add_ann_confirm, pattern="^ann_send_(yes|no)$")],
        },
        fallbacks=fallback,
    )

    conv_add_replnote = ConversationHandler(
        entry_points=[CallbackQueryHandler(ha.add_replnote_start, pattern="^a_add_replnote$")],
        states={
            REPLNOTE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.add_replnote_text)],
            REPLNOTE_CONFIRM: [CallbackQueryHandler(ha.add_replnote_confirm, pattern="^replnote_save_(yes|no)$")],
        },
        fallbacks=fallback,
    )

    conv_set_ph = ConversationHandler(
        entry_points=[CallbackQueryHandler(ha.set_ph_start, pattern="^phset_manual$")],
        states={
            PH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.set_ph_date)],
        },
        fallbacks=fallback,
    )

    conv_add_admin = ConversationHandler(
        entry_points=[CallbackQueryHandler(ha.add_admin_start, pattern="^a_add_admin$")],
        states={
            ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.add_admin_id)],
            ADMIN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.add_admin_name)],
        },
        fallbacks=fallback,
    )

    conv_sched_upload = ConversationHandler(
        entry_points=[CallbackQueryHandler(ha.sched_upload_start, pattern="^sched_upload$")],
        states={
            SCHED_UPLOAD_TEXT: [MessageHandler(filters.Document.ALL, ha.sched_upload_document)],
        },
        fallbacks=fallback,
    )

    conv_sched_field = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ha.sched_field_chosen, pattern="^field_"),
            CallbackQueryHandler(ha.sched_new_pair, pattern="^newpair_"),
        ],
        states={
            SCHED_FIELD_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.sched_field_value)],
        },
        fallbacks=fallback,
    )

    return [
        conv_add_hw, conv_add_ann, conv_add_replnote, conv_set_ph, conv_add_admin,
        conv_sched_upload, conv_sched_field,
    ]


def main():
    db.init_default_schedule()
    db.cleanup_old_schedule_cache(days=30)

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_error_handler(error_handler)

    # Команды
    application.add_handler(CommandHandler("start", hu.start))
    application.add_handler(CommandHandler("myid", hu.my_id))

    # Многошаговые диалоги (регистрируются ДО общих callback-хендлеров)
    for conv in build_conversations():
        application.add_handler(conv)

    # Главное меню / пользовательские разделы
    application.add_handler(CallbackQueryHandler(hu.main_menu_callback, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(hu.back_to_menu_new, pattern="^back_to_menu_new$"))
    application.add_handler(CallbackQueryHandler(hu.show_schedule, pattern="^menu_zam$"))
    application.add_handler(CallbackQueryHandler(hu.show_hw, pattern="^menu_hw$"))
    application.add_handler(CallbackQueryHandler(hu.show_announcements, pattern="^menu_ann$"))
    application.add_handler(CallbackQueryHandler(hu.show_info, pattern="^menu_info$"))

    # Инфо -> подменю (звонки / расписание пар с картинками)
    application.add_handler(CallbackQueryHandler(hu.show_bells_menu, pattern="^info_bells$"))
    application.add_handler(CallbackQueryHandler(hu.show_bells_regular, pattern="^bells_regular$"))
    application.add_handler(CallbackQueryHandler(hu.show_bells_regular_a, pattern="^bells_regular_a$"))
    application.add_handler(CallbackQueryHandler(hu.show_bells_regular_b, pattern="^bells_regular_b$"))
    application.add_handler(CallbackQueryHandler(hu.show_bells_preholiday, pattern="^bells_preholiday$"))
    application.add_handler(CallbackQueryHandler(hu.show_sched_img_menu, pattern="^info_sched_img$"))
    application.add_handler(CallbackQueryHandler(hu.send_schedule_image, pattern="^schedimg_(num|den|cmp)$"))

    # Reply-кнопка «Меню»
    application.add_handler(MessageHandler(
        filters.Regex("^📋 Меню$") & ~filters.COMMAND, hu.handle_menu_reply_button
    ))

    # Админ-панель — верхний уровень и подменю
    application.add_handler(CallbackQueryHandler(ha.admin_panel_entry, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(ha.shift_menu, pattern="^a_shift$"))
    application.add_handler(CallbackQueryHandler(ha.shift_set, pattern="^shiftset_(1|2)$"))
    application.add_handler(CallbackQueryHandler(ha.hw_menu, pattern="^a_hw_menu$"))
    application.add_handler(CallbackQueryHandler(ha.ann_menu, pattern="^a_ann_menu$"))
    application.add_handler(CallbackQueryHandler(ha.ph_menu, pattern="^a_ph_menu$"))
    application.add_handler(CallbackQueryHandler(ha.admins_menu, pattern="^a_admins_menu$"))

    application.add_handler(CallbackQueryHandler(ha.del_hw_list, pattern="^a_del_hw$"))
    application.add_handler(CallbackQueryHandler(ha.del_hw_pick, pattern="^delhw_\\d+$"))
    application.add_handler(CallbackQueryHandler(ha.del_hw_confirm, pattern="^confirm_delhw_\\d+$"))

    application.add_handler(CallbackQueryHandler(ha.del_ann_list, pattern="^a_del_ann$"))
    application.add_handler(CallbackQueryHandler(ha.del_ann_pick, pattern="^delann_\\d+$"))
    application.add_handler(CallbackQueryHandler(ha.del_ann_confirm, pattern="^confirm_delann_\\d+$"))

    application.add_handler(CallbackQueryHandler(ha.set_ph_menu, pattern="^a_set_ph$"))
    application.add_handler(CallbackQueryHandler(ha.set_ph_quick, pattern="^phset_(tomorrow|daftertomorrow)$"))
    application.add_handler(CallbackQueryHandler(ha.unset_ph_list, pattern="^a_unset_ph$"))
    application.add_handler(CallbackQueryHandler(ha.unset_ph_confirm, pattern="^unsetph_\\d+$"))

    application.add_handler(CallbackQueryHandler(ha.del_admin_list, pattern="^a_del_admin$"))
    application.add_handler(CallbackQueryHandler(ha.del_admin_pick, pattern="^deladmin_\\d+$"))
    application.add_handler(CallbackQueryHandler(ha.del_admin_confirm, pattern="^confirm_deladmin_\\d+$"))
    application.add_handler(CallbackQueryHandler(ha.view_admins, pattern="^a_view_admins$"))

    application.add_handler(CallbackQueryHandler(ha.edit_schedule_menu, pattern="^a_sched_menu$"))
    application.add_handler(CallbackQueryHandler(ha.del_all_day_menu, pattern="^a_del_all_day$"))
    application.add_handler(CallbackQueryHandler(ha.sched_by_day_start, pattern="^sched_by_day$"))
    application.add_handler(CallbackQueryHandler(ha.sched_day_chosen, pattern="^schedday_\\d+$"))
    application.add_handler(CallbackQueryHandler(ha.sched_delete_all_day, pattern="^delallday_\\d+$"))
    application.add_handler(CallbackQueryHandler(ha.sched_week_type_chosen, pattern="^weektype_"))
    application.add_handler(CallbackQueryHandler(ha.sched_pair_chosen, pattern="^editpair_"))
    application.add_handler(CallbackQueryHandler(ha.sched_delete_pair, pattern="^delpair_"))
    application.add_handler(CallbackQueryHandler(ha.sched_upload_confirm, pattern="^confirm_schedupload_0$"))

    # Общие отмены/подтверждения, которые не попали в конкретный ConversationHandler
    application.add_handler(CallbackQueryHandler(ha.cancel_conversation, pattern="^cancel_action$"))
    application.add_handler(CallbackQueryHandler(ha.back_to_admin_panel, pattern="^cancel_delhw$"))
    application.add_handler(CallbackQueryHandler(ha.back_to_admin_panel, pattern="^cancel_delann$"))
    application.add_handler(CallbackQueryHandler(ha.back_to_admin_panel, pattern="^cancel_deladmin$"))
    application.add_handler(CallbackQueryHandler(ha.back_to_admin_panel, pattern="^cancel_schedupload$"))

    logger.info("Бот запущен. Health-сервер на порту %s", os.environ.get("PORT", 8000))
    application.run_polling(drop_pending_updates=True)


# ---------- Graceful shutdown ----------
atexit.register(db.close_pool)


if __name__ == "__main__":
    main()
