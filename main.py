import configparser
import os
import traceback
import datetime
import time

from telebot import types

import interlayer
import locales
import logger
import sql_worker
import utils
import threading

from distort import distort_main, distort_init
from qwerty import qwerty_main
from inline import query_text_main


def pre_init():
    config: configparser.ConfigParser
    version = "1.1"
    build = "3"

    if logger.clear_log():
        logger.write_log("INFO: log was cleared successful")

    config = utils.config_init()
    logger.logger_init(config)
    distort_init(config)
    utils.whitelist_init()
    interlayer.translate_init()
    utils.list_of_langs()
    locales.locales_check_integrity(config)
    if locales.locale_data.get("version") != version:
        logger.write_log("WARN: Polyglot and locale versions doesn't match! This can cause the bot to malfunction."
                         "\nPlease, try to check updates for bot or locales file.")
    logger.write_log("###POLYGLOT {} build {} HAS BEEN STARTED###".format(version, build))


pre_init()


def botname_checker(message):  # Crutch to prevent the bot from responding to other bots commands

    if ("@" in message.text and "@" + utils.bot.get_me().username in message.text) or not ("@" in message.text):
        return True
    else:
        return False


def chat_settings_lang(message, auxiliary_text):
    locales_list = locales.locale_data.get("localesList")
    buttons = types.InlineKeyboardMarkup()
    for locale in locales_list:
        try:
            locale_name = locales.locale_data.get(locale).get("fullName")
        except AttributeError as e:
            logger.write_log("ERR: lang parsing failed!")
            logger.write_log("ERR: " + str(e) + "\n" + traceback.format_exc())
            continue
        buttons.add(types.InlineKeyboardButton(text=locale_name, callback_data=locale + " " + auxiliary_text))
    if auxiliary_text == "settings" and message.chat.type != "private":
        buttons.add(types.InlineKeyboardButton(text=locales.get_text(message.chat.id, "backBtn"),
                                               callback_data="back"))
        utils.bot.edit_message_text(locales.get_text(message.chat.id, "chooseLang"), message.chat.id, message.id,
                                    reply_markup=buttons, parse_mode='html')
        return
    utils.bot.reply_to(message, locales.get_text(message.chat.id, "chooseLang"),
                       reply_markup=buttons, parse_mode='html')


@utils.bot.inline_handler(lambda query: len(query.query) >= 0)
def query_text(inline_query):
    query_text_main(inline_query)


@utils.bot.message_handler(commands=['qwerty', 'q'])
def qwerty(message):
    if botname_checker(message):
        qwerty_main(message)


@utils.bot.message_handler(commands=['d', 'distort'])
def distort(message):
    if botname_checker(message):
        threading.Thread(target=distort_main, args=(message,)).start()


@utils.bot.message_handler(commands=['translate', 'trans', 't'])
def translate(message):
    if botname_checker(message):
        inputtext = utils.textparser(message)
        if inputtext is None:
            logger.write_log("none", message)
            return

        logger.write_log(inputtext, message)
        src_lang = None
        message.text = utils.lang_autocorr(message.text)

        if utils.extract_arg(message.text, 2) is not None:
            src_lang = utils.extract_arg(message.text, 1)
            lang = utils.extract_arg(message.text, 2)
        elif utils.extract_arg(message.text, 1) is not None:
            lang = utils.extract_arg(message.text, 1)
        else:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "specifyLang"))
            return

        try:
            inputtext = interlayer.get_translate(inputtext, lang, src_lang=src_lang)
            utils.bot.reply_to(message, inputtext + utils.add_ad(message.chat.id))
        except interlayer.BadTrgLangException:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "badTrgLangException"))
        except interlayer.BadSrcLangException:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "badSrcLangException"))
        except interlayer.TooManyRequestException:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "tooManyRequestException"))
        except interlayer.TooLongMsg:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "tooLongMsg"))
        except interlayer.EqualLangsException:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "equalLangsException"))
        except interlayer.UnkTransException:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "unkTransException"))


@utils.bot.message_handler(commands=['detect'])
def detect(message):
    if not botname_checker(message):
        return

    inputtext = utils.textparser(message)
    if inputtext is None:
        logger.write_log("none", message)
        return

    logger.write_log(inputtext, message)
    try:
        lang = interlayer.lang_list.get(interlayer.extract_lang(inputtext))
        if locales.get_chat_lang(message.chat.id) != "en":
            translated_lang = " (" + interlayer.get_translate(lang, locales.get_chat_lang(message.chat.id)) + ")"
        else:
            translated_lang = ""
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "langDetectedAs").format(lang, translated_lang))
    except (interlayer.BadTrgLangException, interlayer.UnkTransException):
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "langDetectErr"))


@utils.bot.message_handler(commands=['start'])
def send_welcome(message):
    if botname_checker(message):
        logger.write_log(logger.BLOB_TEXT, message)
        chat_info = sql_worker.get_chat_info(message.chat.id)
        if not chat_info:
            chat_settings_lang(message, "start")
            return
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "startMSG"))


@utils.bot.message_handler(commands=['settings'])
def send_welcome(message):
    if botname_checker(message):
        logger.write_log(logger.BLOB_TEXT, message)
        if message.chat.type == "private":
            chat_settings_lang(message, "settings")
        else:
            if btn_checker(message, message.from_user.id):
                utils.bot.reply_to(message, locales.get_text(message.chat.id, "adminsOnly"))
                return
            buttons = types.InlineKeyboardMarkup()
            buttons.add(types.InlineKeyboardButton(text=locales.get_text(message.chat.id, "langBtn"),
                                                   callback_data="chooselang"))
            buttons.add(types.InlineKeyboardButton(text=locales.get_text(message.chat.id, "lockBtn"),
                                                   callback_data="adminblock"))
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "settings"),
                               reply_markup=buttons, parse_mode='html')


@utils.bot.message_handler(commands=['help', 'h'])
def send_help(message):
    if botname_checker(message):
        logger.write_log(logger.BLOB_TEXT, message)
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "helpText"))


@utils.bot.message_handler(commands=['langs', 'l'])
def send_list(message):
    if botname_checker(message):
        logger.write_log(logger.BLOB_TEXT, message)

        try:
            file = open("langlist.txt", "r")
            utils.bot.send_document(message.chat.id, file, message.id,
                                    locales.get_text(message.chat.id, "langList"))
        except FileNotFoundError:
            logger.write_log("WARN: trying to re-create removed langlist file")
            interlayer.list_of_langs()

            if not os.path.isfile("langlist.txt"):
                utils.bot.reply_to(message, locales.get_text(message.chat.id, "langListRemakeErr"))
                return

            file = open("langlist.txt", "r")
            utils.bot.send_document(message.chat.id, file, message.id,
                                    locales.get_text(message.chat.id, "langList"))
        except Exception as e:
            logger.write_log("ERR: langlist file isn't available")
            logger.write_log("ERR: " + str(e) + "\n" + traceback.format_exc())
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "langListReadErr"))


@utils.bot.message_handler(commands=['log'])
def download_log(message):
    if botname_checker(message):
        logger.write_log(logger.BLOB_TEXT, message)
        utils.download_clear_log(message, True)


@utils.bot.message_handler(commands=['clrlog'])
def clear_log(message):
    if botname_checker(message):
        logger.write_log(logger.BLOB_TEXT, message)
        utils.download_clear_log(message, False)


@utils.bot.message_handler(commands=['auto'])
def auto_trans_set(message):
    if not botname_checker(message):
        return

    if not utils.enable_auto:
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "autoTransDisabledConf"))
        return

    disabled = False

    if utils.extract_arg(message.text, 1) is None:
        chat_info = sql_worker.get_chat_info(message.chat.id)
        if not chat_info:
            disabled = True
        if chat_info[0][6] == "disable" or chat_info[0][6] == "" or chat_info[0][6] is None:
            disabled = True
        if disabled:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "autoTransStatus")
                               + locales.get_text(message.chat.id, "premiumStatusDisabled"))
            return

        lang = interlayer.lang_list.get(chat_info[0][6])
        try:
            if locales.get_chat_lang(message.chat.id) != "en":
                translated_lang = lang + " (" + interlayer.get_translate(lang, chat_info[0][6]) + ")"
            else:
                translated_lang = ""
        except (interlayer.BadTrgLangException, interlayer.UnkTransException):
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "langDetectErr"))
            return

        utils.bot.reply_to(message, locales.get_text(message.chat.id, "autoTransStatus")
                           + locales.get_text(message.chat.id, "autoTransLang") + translated_lang)
    else:
        if btn_checker(message, message.from_user.id):
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "adminsOnly"))
            return
        set_lang = utils.lang_autocorr(utils.extract_arg(message.text, 1))
        if interlayer.lang_list.get(set_lang) is None and set_lang != "disable":
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "distortWrongLang"))
        else:
            try:
                sql_worker.write_chat_info(message.chat.id, "target_lang", set_lang)
            except sql_worker.SQLWriteError:
                utils.bot.reply_to(message, locales.get_text(message.chat.id, "configFailed"))
            if set_lang != "disable":
                lang = interlayer.lang_list.get(set_lang)
                try:
                    if locales.get_chat_lang(message.chat.id) != "en":
                        translated_lang = lang + " (" + interlayer.get_translate(lang, set_lang) + ")"
                    else:
                        translated_lang = lang
                except (interlayer.BadTrgLangException, interlayer.UnkTransException):
                    utils.bot.reply_to(message, locales.get_text(message.chat.id, "langDetectErr"))
                    return
                utils.bot.reply_to(message, locales.get_text(message.chat.id, "autoTransSuccess") + translated_lang)
            else:
                utils.bot.reply_to(message, locales.get_text(message.chat.id, "autoTransDisabled"))


def force_premium(message, current_chat):
    if utils.user_admin_checker(message) is False:
        return
    if current_chat[0][3] == "no":
        timer = "0"
        if utils.extract_arg(message.text, 2) is not None:
            try:
                timer = str(int(time.time()) + int(utils.extract_arg(message.text, 2)) * 86400)
            except ValueError:
                utils.bot.reply_to(message, locales.get_text(message.chat.id, "parseTimeError"))
                return
        try:
            sql_worker.write_chat_info(message.chat.id, "premium", "yes")
            sql_worker.write_chat_info(message.chat.id, "expire_time", timer)
        except sql_worker.SQLWriteError:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "premiumError"))
            return
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "forcePremium"))
    else:
        try:
            sql_worker.write_chat_info(message.chat.id, "premium", "no")
            sql_worker.write_chat_info(message.chat.id, "expire_time", "0")
        except sql_worker.SQLWriteError:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "premiumError"))
            return
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "forceUnPremium"))


@utils.bot.message_handler(commands=['premium'])
def premium(message):

    if not botname_checker(message):
        return

    logger.write_log(logger.BLOB_TEXT, message)

    if not utils.enable_ad:
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "adDisabled"))
        return

    sql_worker.actualize_chat_premium(message.chat.id)
    current_chat = sql_worker.get_chat_info(message.chat.id)
    if not current_chat:
        try:
            sql_worker.write_chat_info(message.chat.id, "premium", "no")
        except sql_worker.SQLWriteError:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "premiumError"))
            return
        current_chat = sql_worker.get_chat_info(message.chat.id)

    if utils.extract_arg(message.text, 1) == "force":
        # Usage: /premium force [time_in_hours (optional argument)]
        force_premium(message, current_chat)
        return

    if current_chat[0][3] == "no":
        premium_status = locales.get_text(message.chat.id, "premiumStatusDisabled")
    else:
        if current_chat[0][4] != 0:
            premium_status = locales.get_text(message.chat.id, "premiumStatusTime") + " " + \
                         datetime.datetime.fromtimestamp(current_chat[0][4]).strftime("%d.%m.%Y %H:%M:%S")
        else:
            premium_status = locales.get_text(message.chat.id, "premiumStatusInfinity")

    utils.bot.reply_to(message, locales.get_text(message.chat.id, "premiumStatus") + " <b>" + premium_status + "</b>",
                       parse_mode="html")


@utils.bot.message_handler(commands=['addtask'])
def add_task(message):

    if not botname_checker(message):
        return

    logger.write_log(logger.BLOB_TEXT, message)

    if utils.user_admin_checker(message) is False:
        return

    if not utils.enable_ad:
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "adDisabled"))
        return

    text = utils.textparser(message)
    if text is None:
        return

    if utils.extract_arg(message.text, 1) is None or utils.extract_arg(message.text, 2) is None:
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "taskerArguments"))
        return

    try:
        expire_time = int(time.time()) + int(utils.extract_arg(message.text, 2)) * 86400
    except (TypeError, ValueError):
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "taskerArguments"))
        return

    lang_code = utils.extract_arg(message.text, 1)

    if sql_worker.write_task(message.reply_to_message.id, text, lang_code, expire_time, message.chat.id) is False:
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "taskerFail"))
    else:
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "taskerSuccess").
                           format(lang_code,
                                  datetime.datetime.fromtimestamp(expire_time).strftime("%d.%m.%Y %H:%M:%S")))


@utils.bot.message_handler(commands=['remtask'])
def rm_task(message):
    if not botname_checker(message):
        return

    logger.write_log(logger.BLOB_TEXT, message)

    if utils.user_admin_checker(message) is False:
        return

    if not utils.enable_ad:
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "adDisabled"))
        return

    text = utils.textparser(message)
    if text is None:
        return

    try:
        sql_worker.rem_task(message.reply_to_message.id, message.chat.id)
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "taskerRemSuccess"))
    except sql_worker.SQLWriteError:
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "taskerRemError"))


def btn_checker(message, who_id):
    chat_info = sql_worker.get_chat_info(message.chat.id)
    if chat_info:
        if chat_info[0][2] == "yes":
            status = utils.bot.get_chat_member(message.chat.id, who_id).status
            if status != "administrator" and status != "owner" and status != "creator":
                return True
    return False


@utils.bot.callback_query_handler(func=lambda call: call.data.split()[0] == "chooselang")
def callback_inline_lang_list(call_msg):
    if btn_checker(call_msg.message, call_msg.from_user.id):
        utils.bot.answer_callback_query(callback_query_id=call_msg.id,
                                        text=locales.get_text(call_msg.message.chat.id, "adminsOnly"), show_alert=True)
        return
    chat_settings_lang(call_msg.message, "settings")


@utils.bot.callback_query_handler(func=lambda call: call.data.split()[0] == "adminblock")
def callback_inline_lang_list(call_msg):
    status = utils.bot.get_chat_member(call_msg.message.chat.id, call_msg.from_user.id).status
    if status != "administrator" and status != "owner" and status != "creator":
        utils.bot.answer_callback_query(callback_query_id=call_msg.id,
                                        text=locales.get_text(call_msg.message.chat.id, "adminsOnly"), show_alert=True)
        return
    chat_info = sql_worker.get_chat_info(call_msg.message.chat.id)
    if not chat_info:
        try:
            sql_worker.write_chat_info(call_msg.message.chat.id, "lang", "en")
        except sql_worker.SQLWriteError:
            return
        chat_info = sql_worker.get_chat_info(call_msg.message.chat.id)
    if chat_info[0][2] == "yes":
        set_lock = "no"
    else:
        set_lock = "yes"
    buttons = types.InlineKeyboardMarkup()
    buttons.add(types.InlineKeyboardButton(text=locales.get_text(call_msg.message.chat.id, "backBtn"),
                                           callback_data="back"))
    try:
        sql_worker.write_chat_info(call_msg.message.chat.id, "is_locked", set_lock)
    except sql_worker.SQLWriteError:
        utils.bot.edit_message_text(locales.get_text(call_msg.message.chat.id, "configFailed"),
                                    call_msg.message.chat.id, call_msg.message.id,
                                    reply_markup=buttons, parse_mode="html")
        return
    if set_lock == "yes":
        utils.bot.edit_message_text(locales.get_text(call_msg.message.chat.id, "canSetAdmins"),
                                    call_msg.message.chat.id, call_msg.message.id,
                                    reply_markup=buttons, parse_mode="html")
    else:
        utils.bot.edit_message_text(locales.get_text(call_msg.message.chat.id, "canSetAll"),
                                    call_msg.message.chat.id, call_msg.message.id,
                                    reply_markup=buttons, parse_mode="html")


@utils.bot.callback_query_handler(func=lambda call: call.data.split()[0] == "back")
def callback_inline_back(call_msg):
    if btn_checker(call_msg.message, call_msg.from_user.id):
        utils.bot.answer_callback_query(callback_query_id=call_msg.id,
                                        text=locales.get_text(call_msg.message.chat.id, "adminsOnly"), show_alert=True)
        return
    buttons = types.InlineKeyboardMarkup()
    buttons.add(types.InlineKeyboardButton(text=locales.get_text(call_msg.message.chat.id, "langBtn"),
                                           callback_data="chooselang"))
    buttons.add(types.InlineKeyboardButton(text=locales.get_text(call_msg.message.chat.id, "lockBtn"),
                                           callback_data="adminblock"))
    utils.bot.edit_message_text(locales.get_text(call_msg.message.chat.id, "settings"),
                                call_msg.message.chat.id, call_msg.message.id, reply_markup=buttons, parse_mode='html')


@utils.bot.callback_query_handler(func=lambda call: True)
def callback_inline_lang_chosen(call_msg):
    if call_msg.data.split()[0] == "adminblock" or call_msg.data.split()[0] == "back" \
            or call_msg.data.split()[0] == "chooselang":
        return
    if btn_checker(call_msg.message, call_msg.from_user.id):
        utils.bot.answer_callback_query(callback_query_id=call_msg.id,
                                        text=locales.get_text(call_msg.message.chat.id, "adminsOnly"), show_alert=True)
        return
    try:
        sql_worker.write_chat_info(call_msg.message.chat.id, "lang", call_msg.data.split()[0])
        if call_msg.message.chat.type == "private":
            sql_worker.write_chat_info(call_msg.message.chat.id, "user_id", call_msg.from_user.id)
    except sql_worker.SQLWriteError:
        buttons = types.InlineKeyboardMarkup()
        if call_msg.message.chat.type != "private":
            buttons.add(types.InlineKeyboardButton(text=locales.get_text(call_msg.message.chat.id, "backBtn"),
                                                   callback_data="back"))
        utils.bot.edit_message_text(locales.get_text(call_msg.message.chat.id, "configFailed"),
                                    call_msg.message.chat.id, call_msg.message.id,
                                    reply_markup=buttons, parse_mode="html")
        if call_msg.data.split()[1] == "settings":
            return
    if call_msg.data.split()[1] == "start":
        utils.bot.edit_message_text(locales.get_text(call_msg.message.chat.id, "startMSG"),
                                    call_msg.message.chat.id, call_msg.message.id)
    elif call_msg.data.split()[1] == "settings":
        buttons = types.InlineKeyboardMarkup()
        if call_msg.message.chat.type != "private":
            buttons.add(types.InlineKeyboardButton(text=locales.get_text(call_msg.message.chat.id, "backBtn"),
                                                   callback_data="back"))
        utils.bot.edit_message_text(locales.get_text(call_msg.message.chat.id, "configSuccess"),
                                    call_msg.message.chat.id, call_msg.message.id,
                                    reply_markup=buttons, parse_mode="html")


@utils.bot.message_handler(content_types=["text", "audio", "document", "photo", "video"])
def auto_translate(message):

    if not utils.enable_auto:
        return

    chat_info = sql_worker.get_chat_info(message.chat.id)
    if not chat_info:
        return

    if chat_info[0][6] == "disable" or chat_info[0][6] == "" or chat_info[0][6] is None:
        return

    if message.text is not None:
        inputtext = message.text
    elif message.caption is not None:
        inputtext = message.caption
    elif hasattr(message, 'poll'):
        inputtext = message.poll.question + "\n\n"
        for option in message.poll.options:
            inputtext += "☑️ " + option.text + "\n"
    else:
        return

    try:
        text_lang = interlayer.extract_lang(inputtext)
    except interlayer.UnkTransException:
        utils.bot.reply_to(message, locales.get_text(message.chat.id, "langDetectErr"))
        return

    if text_lang != chat_info[0][6]:
        try:
            utils.bot.reply_to(message, interlayer.get_translate(inputtext, chat_info[0][6]))
        except interlayer.BadTrgLangException:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "badTrgLangException"))
        except interlayer.TooManyRequestException:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "tooManyRequestException"))
        except interlayer.TooLongMsg:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "tooLongMsg"))
        except interlayer.UnkTransException:
            utils.bot.reply_to(message, locales.get_text(message.chat.id, "unkTransException"))


utils.bot.infinity_polling()
