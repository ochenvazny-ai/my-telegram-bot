import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters,
)

import database as db
import handlers_user as hu
import handlers_admin as ha
import schedule_image as sched_img
from config import (
    BOT_TOKEN, HW_TEXT, HW_DUE, ANN_TEXT, ANN_CONFIRM, REPLNOTE_TEXT, REPLNOTE_CONFIRM, PH_DATE,
    SCHED_UPLOAD_TEXT, SCHED_FIELD_VALUE, ADMIN_ID, ADMIN_NAME,
    EXTRA_NAME, EXTRA_CONTENT, SET_GROUP, SET_BOT_NAME, SET_BOT_PHOTO,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def error_handler(update, context):
    logger.error("Необработанное исключение:", exc_info=context.error)


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
        states={PH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.set_ph_date)]},
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
        states={SCHED_UPLOAD_TEXT: [MessageHandler(filters.Document.ALL, ha.sched_upload_document)]},
        fallbacks=fallback,
    )

    conv_sched_field = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ha.sched_field_chosen, pattern="^field_"),
            CallbackQueryHandler(ha.sched_new_pair, pattern="^newpair_"),
        ],
        states={SCHED_FIELD_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.sched_field_value)]},
        fallbacks=fallback,
    )

    conv_extra_add = ConversationHandler(
        entry_points=[CallbackQueryHandler(ha.extra_add_start, pattern="^a_add_extra$")],
        states={
            EXTRA_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.extra_add_name)],
            EXTRA_CONTENT: [
                MessageHandler(filters.PHOTO, ha.extra_add_content_photo),
                MessageHandler(filters.Document.ALL, ha.extra_add_content_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ha.extra_add_content_text),
                CallbackQueryHandler(ha.extra_add_skip_photo, pattern="^extra_skip_photo$"),
            ],
        },
        fallbacks=fallback,
    )

    conv_set_group = ConversationHandler(
        entry_points=[CallbackQueryHandler(ha.set_group_start, pattern="^a_set_group$")],
        states={SET_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.set_group_finish)]},
        fallbacks=fallback,
    )

    conv_set_bot_name = ConversationHandler(
        entry_points=[CallbackQueryHandler(ha.set_bot_name_start, pattern="^a_set_botname$")],
        states={SET_BOT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ha.set_bot_name_finish)]},
        fallbacks=fallback,
    )

    conv_set_bot_photo = ConversationHandler(
        entry_points=[CallbackQueryHandler(ha.set_bot_photo_start, pattern="^a_set_botphoto$")],
        states={SET_BOT_PHOTO: [MessageHandler(filters.PHOTO, ha.set_bot_photo_finish)]},
        fallbacks=fallback,
    )

    return [
        conv_add_hw, conv_add_ann, conv_add_replnote, conv_set_ph, conv_add_admin,
        conv_sched_upload, conv_sched_field,
        conv_extra_add, conv_set_group, conv_set_bot_name, conv_set_bot_photo,
    ]


def main():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    db.init_default_schedule()

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", hu.start))
    application.add_handler(CommandHandler("myid", hu.my_id))

    for conv in build_conversations():
        application.add_handler(conv)

    # Пользовательская часть
    application.add_handler(CallbackQueryHandler(hu.main_menu_callback, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(hu.show_schedule, pattern="^menu_zam$"))
    application.add_handler(CallbackQueryHandler(hu.show_hw, pattern="^menu_hw$"))
    application.add_handler(CallbackQueryHandler(hu.show_announcements, pattern="^menu_ann$"))
    application.add_handler(CallbackQueryHandler(hu.show_extra_classes, pattern="^menu_extra$"))
    application.add_handler(CallbackQueryHandler(hu.extra_class_open, pattern="^open_extra_\\d+$"))
    application.add_handler(CallbackQueryHandler(hu.show_info, pattern="^menu_info$"))

    application.add_handler(CallbackQueryHandler(hu.show_bells_menu, pattern="^info_bells$"))
    application.add_handler(CallbackQueryHandler(hu.show_bells_regular, pattern="^bells_regular$"))
    application.add_handler(CallbackQueryHandler(hu.show_bells_preholiday, pattern="^bells_preholiday$"))
    application.add_handler(CallbackQueryHandler(hu.show_sched_img_menu, pattern="^info_sched_img$"))
    application.add_handler(CallbackQueryHandler(hu.send_schedule_image, pattern="^schedimg_(num|den|cmp)$"))

    application.add_handler(MessageHandler(
        filters.Regex("^📋 Меню$") & ~filters.COMMAND, hu.handle_menu_reply_button
    ))

    # Админка
    application.add_handler(CallbackQueryHandler(ha.admin_panel_entry, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(ha.shift_menu, pattern="^a_shift$"))
    application.add_handler(CallbackQueryHandler(ha.shift_set, pattern="^shiftset_(1|2)$"))
    application.add_handler(CallbackQueryHandler(ha.hw_menu, pattern="^a_hw_menu$"))
    application.add_handler(CallbackQueryHandler(ha.ann_menu, pattern="^a_ann_menu$"))
    application.add_handler(CallbackQueryHandler(ha.ph_menu, pattern="^a_ph_menu$"))
    application.add_handler(CallbackQueryHandler(ha.admins_menu, pattern="^a_admins_menu$"))
    application.add_handler(CallbackQueryHandler(ha.extra_menu, pattern="^a_extra_menu$"))
    application.add_handler(CallbackQueryHandler(ha.bot_settings_menu, pattern="^a_bot_settings$"))

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

    application.add_handler(CallbackQueryHandler(ha.extra_del_list, pattern="^a_del_extra$"))
    application.add_handler(CallbackQueryHandler(ha.extra_del_pick, pattern="^delextra_\\d+$"))
    application.add_handler(CallbackQueryHandler(ha.extra_del_confirm, pattern="^confirm_delextra_\\d+$"))
    application.add_handler(CallbackQueryHandler(ha.extra_view, pattern="^a_view_extra$"))

    application.add_handler(CallbackQueryHandler(ha.edit_schedule_menu, pattern="^a_sched_menu$"))
    application.add_handler(CallbackQueryHandler(ha.del_all_day_menu, pattern="^a_del_all_day$"))
    application.add_handler(CallbackQueryHandler(ha.sched_by_day_start, pattern="^sched_by_day$"))
    application.add_handler(CallbackQueryHandler(ha.sched_day_chosen, pattern="^schedday_\\d+$"))
    application.add_handler(CallbackQueryHandler(ha.sched_delete_all_day, pattern="^delallday_\\d+$"))
    application.add_handler(CallbackQueryHandler(ha.sched_week_type_chosen, pattern="^weektype_"))
    application.add_handler(CallbackQueryHandler(ha.sched_pair_chosen, pattern="^editpair_"))
    application.add_handler(CallbackQueryHandler(ha.sched_delete_pair, pattern="^delpair_"))
    application.add_handler(CallbackQueryHandler(ha.sched_upload_confirm, pattern="^confirm_schedupload_0$"))

    application.add_handler(CallbackQueryHandler(ha.cancel_conversation, pattern="^cancel_action$"))
    application.add_handler(CallbackQueryHandler(ha.back_to_admin_panel, pattern="^cancel_delhw$"))
    application.add_handler(CallbackQueryHandler(ha.back_to_admin_panel, pattern="^cancel_delann$"))
    application.add_handler(CallbackQueryHandler(ha.back_to_admin_panel, pattern="^cancel_deladmin$"))
    application.add_handler(CallbackQueryHandler(ha.back_to_admin_panel, pattern="^cancel_delextra$"))
    application.add_handler(CallbackQueryHandler(ha.back_to_admin_panel, pattern="^cancel_schedupload$"))

    logger.info("Бот запущен. Health-сервер на порту %s", os.environ.get("PORT", 8000))
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()