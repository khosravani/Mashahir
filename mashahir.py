#! /usr/local/bin/python3.5  -*- coding: UTF-8 -*-

import asyncio
import ssl
import base64
from datetime import datetime
import numpy as np
import pickle
from urllib.request import urlopen
import requests
from random import shuffle
from aiohttp import web
import subprocess
import telepot
import os.path
import json
# from subprocess import call
from telepot.aio.delegate import *
from telepot.namedtuple import *
import config

class OwnerHandler(telepot.aio.helper.ChatHandler):
    def __init__(self, seed_tuple, store, info, feedback, **kwargs):
        super(OwnerHandler, self).__init__(seed_tuple, **kwargs)
        self._store = store
        self._info = info
        self._feedback = feedback
        self._step = ''
        # self._mode = 'user'
        self._tmp = 0
        self._spk_id = ''
        self._enrol_id = ''
        self._spk_name = ''
        self._category = ''
        self._help = (
            "Hi master\nYou can control me by sending these commands:\n"
            "/msgs_per_id : to see the number of messages per chat id\n"
            "/chat_ids : to view a list of chat ids with username\n"
            "/msgs_id : to view a list of messages for a chat id\n"
            "/count_ids : to see how many unique ids enrolled\n"
            "/count_recs : to see how many recordings submitted\n"
            "/recs_per_id : to see the number of recordings per chat id\n"
            "/recs_id : to listen to recordings of a chat id\n"
            "/list_spks : list all the reference speakers with their category.\n"
            "/send_id : send message to a specific chat id.\n"
            "/send_all : send message to all chat ids.\n"
            "/feedback_score : the score obtained from feedbacks (out of 5).\n"
            "/feedback_view : view feedback by an id.\n"
            "/feedback_ids : shows all ids with the number of feedback each.\n"
            "/validate_stat: show the status of the recording validation.\n")

    async def on__idle(self, event):
        self.close()

    async def open(self, initial_msg, seed):
        content_type, chat_type, chat_id = telepot.glance(initial_msg)
        if content_type == 'text' and initial_msg['text'].lower() == 'dezh@master':
            await self.sender.sendMessage(self._help)
        else:
            await self.close()
        return True

    async def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        if content_type == 'text' and msg['text'].lower() == 'dezh@user':
            self.close()

        if content_type != 'text':
            await self.sender.sendMessage(self._help)
            return False

        command = msg['text'].strip().lower()

        # Tells who has sent you how many messages
        if command == '/msgs_per_id':
            results = self._store.msgs_per_chat()

            lines = []
            count = 0
            length = 0
            for r in results:
                count += r[1]
                n = '{0[0]} : {0[1]}'.format(r)
                if length + len(n) + 1 > 4096:
                    await self.sender.sendMessage('\n'.join(lines))
                    lines = []
                    length = 0
                length += len(n) + 1
                lines.append(n)
            lines.append('Total: ' + str(count))
            if len(lines) == 1:
                await self.sender.sendMessage('No chat available.')
            else:
                await self.sender.sendMessage('\n'.join(lines))

        # show all unique ids with username
        elif command == '/chat_ids':
            results = self._store.chat_ids()

            if len(results) < 1:
                await self.sender.sendMessage('No ID found!')
                return

            lines = []
            length = 0
            for k, v in enumerate(results):
                n = 'N{}- {}: {}'.format(k, v[0], v[1])
                if length + len(n) + 1 > 4096:
                    await self.sender.sendMessage('\n'.join(lines))
                    lines = []
                    length = 0
                length += len(n) + 1
                lines.append(n)
            await self.sender.sendMessage('\n'.join(lines))

        # show messages of specified id
        elif command == '/msgs_id':
            await self.sender.sendMessage('Enter the chat id please:')
            self._step = 'msg_1'
            return

        elif command == '/count_ids':
            await self.sender.sendMessage(
                'Unique IDs: ' + str(self._store.count_ids())
            )

        elif command == '/count_recs':
            count = 0
            for ids in self._info.keys():
                count += len(self._info[ids])
            await self.sender.sendMessage(
                'Number of recordings: ' + str(count)
            )
        elif command == '/recs_per_id':
            if len(self._info.items()) > 0:
                lines = []
                length = 0
                for k, v in self._info.items():
                    n = '{}: {}'.format(k, len(v))
                    if length + len(n) + 1 > 4096:
                        await self.sender.sendMessage('\n'.join(lines))
                        lines = []
                        length = 0
                    length += len(n) + 1
                    lines.append(n)
                await self.sender.sendMessage('\n'.join(lines))
            else:
                await self.sender.sendMessage('no record found!')

        elif command == '/recs_id':
            await self.sender.sendMessage('Enter the chat id please:')
            self._step = 'rec_1'
            return

        elif command == '/send_id':
            await self.sender.sendMessage('Enter the speaker ID:')
            self._step = 'send_id_1'
            return

        elif command == '/send_all':
            await self.sender.sendMessage('Enter your message:')
            self._step = 'send_all'
            return
        elif command == '/feedback_score':
            await self.sender.sendMessage(
                str(self._feedback.score_feedback()) +
                " out of " + str(self._feedback.count_feedbacks()) + " feedbacks"
            )
            return
        elif command == '/feedback_view':
            await self.sender.sendMessage('Enter the chat id please:')
            self._step = 'feedback_1'
            return
        elif command == '/feedback_ids':
            lines = []
            length = 0
            n = 0
            for chat_id, v in self._feedback.get_ids():
                if len(v) > 0:
                    record = (
                        'No.' + str(n + 1) + "- " + str(chat_id) +
                        ": " + v[0]['first_name'] +
                        " " + v[0]['last_name'] +
                        ", " + v[0]['username']
                    )
                    if length + len(record) + 1 > 4096:
                        await self.sender.sendMessage('\n'.join(lines))
                        lines = []
                        length = 0
                    length += len(record) + 1
                    lines.append(record)
                    n += 1
            if n < 1:
                await self.sender.sendMessage("No id found!")
            else:
                await self.sender.sendMessage('\n'.join(lines))
            return True

        elif command == '/validate_stat':
            undone, total, valid_stat = 0, 0, {}
            for i in validation_list:
                valid_stat[i] = 0
            for chat_id in self._info:
                for record in self._info[chat_id]:
                    total += 1
                    if not record['valid']:
                        undone += 1
                    else:
                        valid_stat[record['valid']] += 1
           
            resp = "Undone: {} out of {}\n".format(undone, total)
            for i in validation_list:
                resp += "{}: {}\n".format(validation_list[i], valid_stat[i]) 
            await self.sender.sendMessage(resp)

                    
        elif self._step == 'msg_1':
            if command.isdigit() and self._store.exist(int(command)):
                self._tmp = int(command)
                await self.sender.sendMessage(
                    'How many text messages to show?'
                )
                self._step = 'msg_2'
                return
            else:
                await self.sender.sendMessage('No such id found.')
        elif self._step == 'msg_2':
            if command.isdigit() and int(command) > 0:
                results = self._store.pull(self._tmp, int(command))
                lines = []
                for v in results:
                    if 'text' in v.keys():
                        n = '{}'.format(v['text'])
                    else:
                        n = '--'
                    lines.append(n)
                await self.sender.sendMessage('\n'.join(lines))
            else:
                await self.sender.sendMessage('Not a valid number!')

        elif self._step == 'rec_1':
            if command.isdigit() and int(command) in self._info:
                self._tmp = int(command)
                await self.sender.sendMessage(
                    'How many voice messages to show?'
                )
                self._step = 'rec_2'
                return
            else:
                await self.sender.sendMessage('No such id found.')

        elif self._step == 'rec_2':
            if command.isdigit() and int(command) > 0:
                results = self._info[self._tmp]
                count = int(command)
                for v in reversed(results):
                    if count > 0:
                        await self.sender.sendVoice(v['file_id'])
                        count -= 1
            else:
                await self.sender.sendMessage('Not a valid number!')

        elif self._step == 'send_id_1':
            self._spk_id = msg['text']
            await self.sender.sendMessage('Enter your message:')
            self._step = 'send_id_2'
            return
        elif self._step == 'send_id_2':
            try:
                await bot.sendMessage(self._spk_id, msg['text'])
                await self.sender.sendMessage("Done.")
            except Exception as inst:
                await self.sender.sendMessage(inst)

        elif self._step == 'send_all':
            n = 0
            m = 0
            inactive = set()
            for spk in self._seen:
                try:
                    await bot.sendMessage(spk, msg['text'])
                    n += 1
                except Exception as inst:
                    inactive.add(spk)
                    m += 1
                    await self.sender.sendMessage("Exception: " + str(spk))
            await self.sender.sendMessage(
                "The message was sent to " + str(n) + " IDs. " + str(m) + " were removed."
            )
            self._seen = self._seen - inactive
        elif self._step == 'feedback_1':
            if command.isdigit() and self._feedback.exist(int(msg['text'])):
                self._tmp = int(msg['text'])
                await self.sender.sendMessage(
                    'How many text messages to show?'
                )
                self._step = 'feedback_2'
                return
            else:
                await self.sender.sendMessage('No such id found.')
        elif self._step == 'feedback_2':
            if command.isdigit() and int(msg['text']) > 0:
                results = self._feedback.pull(self._tmp, int(msg['text']))
                for v in results:
                    if 'text' in v:
                        await self.sender.sendMessage('{}\n'.format(v['text']))
            else:
                await self.sender.sendMessage('Not a valid number!')
        else:
            await self.sender.sendMessage(self._help)

        self._step = ''
        return


class EditorHandler(telepot.aio.helper.ChatHandler):
    def __init__(self, seed_tuple, info, **kwargs):
        super(EditorHandler, self).__init__(seed_tuple, **kwargs)
        self._info = info
        self._confirmed = False
        self._help = (
            "خانم احمدی عزیز\nلطفا از میان گزینه‌های موجود مناسب‌ترین را پس از گوش دادن به فایل صوتی و مقایسه آن با متن ارائه شده انتخاب کنید."
        )
        self.record = ''

    async def on__idle(self, event):
        self.close()

    async def open(self, initial_msg, seed):
        content_type, chat_type, chat_id = telepot.glance(initial_msg)
        await self.nextRecord()
        if self.record:
            await self.sender.sendMessage(self._help, reply_markup=confirmation)
        else:
            await self.sender.sendMessage("در حال حاضر رکوردی موجود نیست.")
            self.close()
        return True

    async def nextRecord(self):
        print("In nextRecord")
        self.record = ''
        for chat_id in self._info:
            for k, record in enumerate(self._info[chat_id]):
                if not record['valid']:
                    self.record = record
                    return

    async def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        if content_type != 'text':
            await self.sender.sendMessage("متوجه نمیشوم!")
            return
        choice = msg['text']

        if not self._confirmed:
            if choice != 'موافقم 👍':
                await self.sender.sendMessage(self._help, reply_markup=confirmation)
                return
            else:
                self._confirmed = True
                if self.record['prompt']:
                    await self.sender.sendVoice(self.record['file_id'])
                    await self.sender.sendMessage(self.record['prompt'], reply_markup=validation)
                else:
                    await self.sender.sendVoice(self.record['file_id'])
                    await self.sender.sendMessage('این فایل بدون متن میباشد، لطفا از موارد زیر یکی را انتخاب نمایید:', reply_markup=validation)
                return
        
        if choice in inv_validation_list:
            self.record['valid'] = inv_validation_list[choice]
            await self.nextRecord()
            await self.sender.sendMessage('👍')
            if self.record:
                if self.record['prompt']:
                    await self.sender.sendVoice(self.record['file_id'])
                    await self.sender.sendMessage(self.record['prompt'], reply_markup=validation)
                else:
                    await self.sender.sendVoice(self.record['file_id'])
                    await self.sender.sendMessage('این فایل بدون متن میباشد، لطفا از موارد زیر یکی را انتخاب نمایید:', reply_markup=validation)
            else:
                await self.sender.sendMessage('تمام شد. ممنونم 😇')
                self.close()
        return


# Simulate a database to store unread messages
class UnreadStore(object):
    def __init__(self):
        if os.path.exists(CHATDBPATH):
            with open(CHATDBPATH, 'rb') as chatdb:
                self._db = pickle.load(chatdb)
        else:
            self._db = {}

    def put(self, msg):
        chat_id = msg['chat']['id']
        if chat_id not in self._db:
            self._db[chat_id] = []

        self._db[chat_id].append(msg)

    def exist(self, chat_id):
        return True if chat_id in self._db.keys() else False

    # Pull the last num unread messages of a `chat_id`
    def pull(self, chat_id, num=None):
        messages = self._db[chat_id]

        # sort by date
        messages.sort(key=lambda m: m['date'])
        if num is None:
            return messages
        else:
            return messages[-min(num, len(messages)):]

    # Tells how many messages per chat_id
    def msgs_per_chat(self):
        return [(k, len(v)) for k, v in self._db.items()]

    # Pull all chat_ids
    def chat_ids(self):
        chat_names = []
        for k, v in self._db.items():
            first_name = v[0]['from']['first_name'] if 'first_name' in v[0]['from'] else ''
            last_name = v[0]['from']['last_name'] if 'last_name' in v[0]['from'] else ''
            username = v[0]['from']['username'] if 'username' in v[0]['from'] else ''

            chat_names.append(
                (k, first_name + " " + last_name + ", " + username, v[0]['date'])
            )
        chat_names.sort(key=lambda m: m[2])
        return chat_names

    # Count chat_ids
    def count_ids(self):
        return len(self._db.items())

    # remove chat_ids
    def remove_id(self, chat_id):
        self._db.pop(chat_id, None)
        return

    # Save database to the file
    def savedb(self):
        with open(CHATDBPATH, 'wb') as chatdb:
            pickle.dump(self._db, chatdb)


# Simulate a database to store feedbacks
class FeedbackStore(object):
    def __init__(self):
        if os.path.exists(FEEDBACKPATH):
            with open(FEEDBACKPATH, 'rb') as feedback:
                self._feedback = pickle.load(feedback)
        else:
            self._feedback = {}

    def put(self, msg):
        chat_id = msg['from']['id']
        if chat_id not in self._feedback:
            self._feedback[chat_id] = []

        first_name = msg['from']['first_name'] if 'first_name' in msg['from'] else ''
        last_name = msg['from']['last_name'] if 'last_name' in msg['from'] else ''
        username = msg['from']['username'] if 'username' in msg['from'] else ''
        if 'data' in msg:
            self._feedback[chat_id].append({
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'date': datetime.fromtimestamp(int(msg['message']['date'])).strftime('%Y-%m-%d %H:%M:%S'),
                'feedback': msg['data']
            })
        elif 'text' in msg:
            self._feedback[chat_id].append({
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'date': datetime.fromtimestamp(int(msg['date'])).strftime('%Y-%m-%d %H:%M:%S'),
                'text': msg['text']
            })

    def exist(self, chat_id):
        if chat_id in self._feedback.keys():
            return True
        return False

    def get_ids(self):
        return self._feedback.items()

    # Pull the last num feedbacks of a user
    def pull(self, chat_id, num=None):
        messages = self._feedback[chat_id]

        # sort by date
        messages.sort(key=lambda m: m['date'])
        if num is None:
            return messages
        else:
            return messages[-min(num, len(messages)):]

    # Count the number of users who sent feedback
    def count_ids(self):
        return len(self._feedback.items())

    # Count the number of users who sent feedback
    def score_feedback(self):
        score = 0.0
        count = 0.0
        for k, v in self._feedback.items():
            for w in v:
                if 'feedback' in w:
                    score += int(w['feedback'])
                    count += 1
        return format(score / count, '0.2f') if count > 0 else score

    # Count the number of feedbacks
    def count_feedbacks(self):
        count = 0
        for k, v in self._feedback.items():
            count += len(v)
        return count

    # remove chat_ids
    def remove_id(self, chat_id):
        self._feedback.pop(chat_id, None)
        return

    # Save feedbacks to the file
    def savefeedback(self):
        with open(FEEDBACKPATH, 'wb') as feedback:
            pickle.dump(self._feedback, feedback)


class MessageSaver(telepot.aio.helper.Monitor):
    def __init__(self, seed_tuple, store, info, feedback, consent, exclude):
        # The `capture` criteria means to capture all messages.
        super(MessageSaver, self).__init__(
            seed_tuple,
            capture=[[lambda msg: not telepot.is_event(msg)]]
        )
        self._store = store
        self._info = info
        self._consent = consent
        self._exclude = exclude
        self._feedback = feedback
        self._time = datetime.now()

    async def on_inline_query(self, msg):
        print('Inline:', msg)
        return
        # await bot.answerInlineQuery(msg['id'], results=[], switch_pm_text='بزن بریم!')

    async def on_callback_query(self, msg):
        return

    # Store every message.
    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)

        now_time = datetime.now()
        if((now_time - self._time).total_seconds() > save_time):
            self._time = now_time
            self._store.savedb()
            self._feedback.savefeedback()
            # TODO: Handle disk error when disk is full. a.khosravani 960526
            with open(CONSENTPATH, 'wb') as consentids:
                pickle.dump(self._consent, consentids)
            with open(JSONPATH, 'wb') as outfile:
                pickle.dump(self._info, outfile)
        self._store.put(msg)
        if chat_id in self._exclude:
            print('Master:', msg)
        else:
            print('Storing: %s' % msg)


class Mashahir(telepot.aio.helper.ChatHandler):
    def __init__(self, seed_tuple, store, info, feedback, consent, **kwargs):
        super(Mashahir, self).__init__(seed_tuple, **kwargs)
        self._store = store
        self._info = info
        self._feedback = feedback
        self._consent = consent
        self._mode = 'user'
        self._owner = True
        self._try = 3
        self._retry = False
        self._idx = np.arange(8)
        self._text = ''
        self._category = ''
        self._state = {"comment": False, "diff": False, "similar": False, "consent": False, "send_reply": False, 'send_voice': False}
        self._message = ''
        self._spkinfo = {}
        self._json = {}
        self._param = {}
        self._reply_spk = 0
        self._reply_message_id = 0
        self.router.routing_table['_getFeedback'] = self.on__getFeedback
        self.router.routing_table['_findSimilarVoice'] = self.on__findSimilarVoice
        self.router.routing_table['_checkVoiceOwner'] = self.on__checkVoiceOwner

    async def on__idle(self, event):
        self.close()

    async def open(self, initial_msg, seed):

        first_name = initial_msg['from']['first_name'] if 'first_name' in initial_msg['from'] else ''
        last_name = initial_msg['from']['last_name'] if 'last_name' in initial_msg['from'] else ''
        username = initial_msg['from']['username'] if 'username' in initial_msg['from'] else ''

        with open(RULESPATH) as record:
            self.rules = record.readlines()

        with open(GOODBYEPATH, 'r') as record:
            self.goodbye = record.readlines()
        
        content_type, chat_type, chat_id = telepot.glance(initial_msg)
        if content_type == 'text' and initial_msg['text'].lower() == 'dezh@master':
            self._mode = 'master'
            return True

        resp = requests.post(
            url_main + '/user/add',
            data={
                'username': str(chat_id),
                'fullname': first_name + ' ' + last_name, 
                'type': 'mashahir_user',
                'description': username},
            verify=False)

        if resp.status_code == 200:
            with open(WELCOMEPATH) as record:
                self.welcome = record.readlines()
            await self.sender.sendMessage(
                ''.join(self.welcome),
                reply_markup=confirmation
            )
            
        elif resp.status_code == 400:
            with open(WELCOMEBACKPATH) as record:
                self.welcomeback = record.readlines()
            
            date = datetime.fromtimestamp(int(initial_msg['date'])).strftime('%H')
            if int(date) > 4 and int(date) < 12:
                await self.sender.sendSticker("CAADBAADRAEAAimanQVWuYi0-8q7rAI")
            elif int(date) > 19 or int(date) <= 4:
                await self.sender.sendSticker("CAADBAADfgEAAimanQXoAafVVrKJigI")
            else:
                await self.sender.sendSticker("CAADBAADQgEAAimanQW-RCpwWqDe-AI")
            await self.sender.sendMessage(
                ''.join(self.welcomeback),
                reply_markup=category
            )

        return True

    async def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        first_name = msg['from']['first_name'] if 'first_name' in msg['from'] else ''
        last_name = msg['from']['last_name'] if 'last_name' in msg['from'] else ''
        username = msg['from']['username'] if 'username' in msg['from'] else ''

        date = datetime.fromtimestamp(int(msg['date'])).strftime('%Y-%m-%d %H:%M:%S')

        resp = requests.post(
            url_main + '/user/add',
            data={
                'username': str(chat_id), 
                'fullname': first_name + ' ' + last_name, 
                'type': 'mashahir_user',
                'description': username},
            verify=False)
        if resp.status_code == 200:
            if msg['text'] == 'موافقم 👍':
                await self.sender.sendMessage(
                    ''.join(self.rules),
                    reply_markup=category
                )
            else:
                await self.sender.sendMessage(
                    'آیا با شرایط ما موافقید؟',
                    reply_markup=confirmation
                )
            return True
        elif resp.status_code == 400:
            resp = requests.post(
                url_main + '/user/update',
                data={
                    'username': str(chat_id),
                    'fullname': first_name + ' ' + last_name,
                    'description': username},
                verify=False)

        if content_type == 'text' and msg['text'].lower() == 'dezh@master':
            self._mode = 'master'
            return

        if content_type == 'text' and msg['text'].lower() == 'dezh@user':
            if self._mode == 'master':
                await self.sender.sendMessage('به بخش کاربری منتقل میشوید.')
                self.close()
            else:
                await self.sender.sendMessage('اینجا بخش کاربری است.')
                return False

        if self._mode == 'master':
            return True
            
        # if the message is a comment
        if self._state["comment"]:
            self._state["comment"] = False
            if (
                content_type == 'text' and 
                'reply_to_message' in msg and 
                msg['reply_to_message']['from']['id'] == 370144284):
                self._feedback.put(msg)
                await self.sender.sendSticker("CAADBAADnwEAAimanQXcPkdWudco_AI")
            await self.tryAgain() # its done. try again
            return True
        
        # if the voice seems to be from another speaker
        if self._state["diff"]:
            self._state["diff"] = False
            # if speaker is not the owner
            if content_type == 'text' and msg['text'] == 'خیر':
                self._owner = False
                self._json['spkid'] = 0

            self.scheduler.event_later(3,('_getFeedback', {'seconds': 3}))
            return

        if self._state["similar"]:
            self._state["similar"] = False
            if content_type == 'text' and msg['text'] == 'بلی':
                self._other_json['spkid'] = chat_id
                self._other_json['first_name'] = self._spkinfo['first_name']
                self._other_json['last_name'] = self._spkinfo['last_name']
                self._other_json['username'] = self._spkinfo['username']
                await self.sender.sendSticker('CAADBAADdAEAAimanQVm3mwt83uLjAI')
                await self.sender.sendMessage('مورد بعدی ...')
                self.scheduler.event_later(1,('_findSimilarVoice', {'seconds': 1}))
                # self._json['spkid'] = other_json['chat_id']
            else:
                await self.sender.sendMessage('اطلاعات این کاربر یافت نشد. مورد بعدی ...')
                self.scheduler.event_later(1,('_findSimilarVoice', {'seconds': 1}))
            return

        if self._retry:
            if 'text' in msg and msg['text'] == 'خیر':
                await self.sender.sendMessage(''.join(self.goodbye))
                self.close()

            await self.sender.sendSticker("CAADBAADTgEAAimanQXH3xQ0uQow4gI")
            await self.sender.sendMessage(
                'خوشحال شدن از خوش آمدن شما ❤️. یکبار دیگر انتخاب کردن:',
                reply_markup=category
            )
            self._retry = False
            return True

        if not self._category:
            if (content_type == 'text' and msg['text'] in category_list.keys()):
                self._category = category_list[msg['text']]
            else:
                await self.sender.sendSticker(
                    "CAADBAADggEAAimanQXyPlRhFuqSigI"
                )
                await self.sender.sendMessage(
                    'ادامه دادن بعد از انتخاب کردن! 😶',
                    reply_markup=category
                )
                return False

        if content_type != 'voice':
            if self._try == 3:
                resp = requests.get(
                    url_main + '/prompt/get',
                    verify=False)
                if resp.status_code == 200:
                    resp = json.loads(resp.content.decode('utf-8'))
                    self._prompt = resp['msg']['prompt']
                    await self.sender.sendSticker(
                        "CAADBAADgAEAAimanQW9Y56OK0mYlAI"
                    )
                    await self.sender.sendMessage(
                        'شمرده و بلند خواندن کلمات زیر و ارسال کردن 👇\n\n' +
                        self._prompt.replace(' ', '\n') + "\n👆🏻"
                    )
                    self._try -= 1
                else:
                    await self.sender.sendSticker(
                        "CAADBAADYAEAAimanQUXP6q2tPbaMwI"
                    )
                    await self.sender.sendMessage(
                        "آ آ آ ه ه ه... نتوانستن در فکر کردن. تعطیل شدن مخ. لطفاً در زمان دیگری سعی کردن."
                    )
                    await self.tryAgain()
                
                return False
            elif self._try == 0:
                await self.sender.sendSticker(
                    "CAADBAADegEAAimanQWSmdWUMxCOlgI"
                )
                await self.tryAgain()
                return False
            else:
                self._try -= 1
                await self.sender.sendSticker(
                    "CAADBAADggEAAimanQXyPlRhFuqSigI"
                )                
                await self.sender.sendMessage(
                    'نخواندن کلمات و نتوانستن در گفتن 😳\n\n' + self._prompt.replace(' ', '\n') + "\n👆🏻"
                )
                return False
        else:
            fileid = msg[content_type]['file_id']
            if int(msg['voice']['duration']) < 4:
                await self.sender.sendSticker("CAADBAADUAEAAimanQWK8QhNwbOY3gI")
                await self.sender.sendMessage(
                    'مگر مسابقه دادن 😳! فرستادن دوباره 😕.\n\n' + self._prompt.replace(' ', '\n') + "\n👆🏻"
                )
                return False

            await self.sender.sendSticker("CAADBAADXAEAAimanQUi_bd4R3Y97QI")
            dest = VOICEPATH + str(chat_id) + "_"
            dest += str(msg['message_id']) + ".opus"

            f = await bot.getFile(fileid)
            result = subprocess.Popen(
                [
                    'bash',
                    GETFILEPATH,
                    dest,
                    f['file_path'],
                    bot._token
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            result.communicate()
            resp = requests.post(
                url_main + '/recognition/identify',
                data={
                    'username': int(chat_id), 
                    'type': self._category,
                    'file_id': fileid,
                    'message_id': msg['message_id'],
                    'prompt': self._prompt},
                files={'audio': (dest, open(dest, 'rb'), 'audio/ogg')},
                verify=False
            )
            if resp.status_code == 200:
                resp = json.loads(resp.content.decode('utf-8'))
                for r in resp['msg']['results']:
                    await self.sender.sendMessage(u'نام: ' + r['fullname'] + u'\nامتیاز: ' + str(r['score']))
                    
                    await self.sender.sendAudio(
                        urlopen(url_main + '/voice/ref/download?id=' + str(r['ref_id']), context=ctx),
                        title=r['fullname'])
                    # if r['avatar_id']:
                    #     await self.sender.sendPhoto(r['avatar_id'])
                    # else:
                    # await self.sender.sendPhoto(urlopen(url_main + '/user/avatar/' + r['username'], context=ctx))
                    
                    # if r['file_id']:
                    #     await self.sender.sendAudio(r['file_id'])
                    # else:
                    
                    break
                    
                else:
                    await self.sender.sendMessage(u'موردی یافت نشد')
            else:
                await self.sender.sendSticker(
                    "CAADBAADYAEAAimanQUXP6q2tPbaMwI"
                )
                await self.sender.sendMessage(
                    "آ آ آ ه ه ه... نتوانستن در فکر کردن. تعطیل شدن مخ. لطفاً در زمان دیگری سعی کردن."
                )
                await self.tryAgain()
            return

    async def reportScore(self):
        spk = self._param['ref'][0]['spk']
        score = self._param['ref'][0]['score']
        if score < 0:
            message = (
                "متاسفانه شباهتی یافت نشد 😢\n" +
                "لطفاً دوباره امتحان کنید و سعی کنید به موارد زیر دقت کنید:\n" +
                "۱. جملات را صحیح، رسا و شمرده ادا کنید.\n" +
                "۲. سعی کنید در محیط بدون سروصدا صحبت کنید."
            )
        elif score < 50:
            message = (
                "بیشترین شباهت صدای شما به ترتیب به:\n۱. {}\n۲. {}\n۳. {}".format(
                    self._param['ref'][0]['spk'], 
                    self._param['ref'][1]['spk'],
                    self._param['ref'][2]['spk'])
            )
        else:
            message = "شک ندارم شما {} هستید 😍.".format(spk)

        await self.sender.sendMessage(message)
        self._param['feedback'] = score > 0
        if self._param['owner']:
            self.scheduler.event_later(3, ('_checkVoiceOwner', {'seconds': 3}))
        # elif self._param['similar']:
        #     self.scheduler.event_later(3, ('_findSimilarVoice', {'seconds': 3}))
        elif self._param['feedback']:
            self.scheduler.event_later(3, ('_getFeedback', {'seconds': 3}))
        else:
            await self.tryAgain()
        return True

    async def on__checkVoiceOwner(self, event):
        chat_id = self._spkinfo['chat_id']
        jsonList = self._info[chat_id]
        file_id = jsonList[0]['file_id']
        message_id = jsonList[0]['message_id']
        for k in reversed(range(self._param['jsonidx'])):
            if jsonList[k]['spkid'] == chat_id:
                file_id = jsonList[k]['file_id']
                message_id = jsonList[k]['message_id']
                break

        for record in self._param['owner']:
            if record["score"] < 0.0 and record["fid"] == file_id:
                await self.sender.sendVoice(
                    file_id,
                    caption='آیا شما صاحب این حساب هستید؟',
                    reply_to_message_id=message_id,
                    reply_markup=yesno
                )
                self._state["diff"] = True
                return

        # if self._owner and self._param['similar']:
        #     self.scheduler.event_later(3,('_findSimilarVoice', {'seconds': 3}))
        if self._param['feedback']:
            self.scheduler.event_later(3,('_getFeedback', {'seconds': 3}))
        else:
            await self.tryAgain()
        return

    async def on__findSimilarVoice(self, event):
        # Check whether he/she did consent for using his/her recordings
        chat_id = self._spkinfo['chat_id']
        if chat_id not in self._consent:
            await self.sender.sendMessage(
                "آیا مایل هستید به شبکه ارتباط صوتی ما بپیوندید؟",
                reply_markup=yesno
            )
            self._state["consent"] = True
            return
        else:
            for record in self._param['similar']:
                if record["score"] > 0.0 and record['chatid'] in self._info:
                    for other_json in self._info[record['chatid']]:
                        if other_json['file_id'] == record['fid'] and other_json['spkid'] != chat_id and other_json['prompt'] != '':
                            if record["score"] > 30:
                                await self.sender.sendVoice(
                                    record["fid"],
                                    caption='صدایی بسیار شبیه صدای شما یافت شد؟ آیا این صدای شماست؟',
                                    reply_markup=yesno
                                )
                            else:
                                await self.sender.sendVoice(
                                    record["fid"],
                                    caption='مشابه‌ترین صدا به صدای شما یافت شد. آیا این صدای شماست؟',
                                    reply_markup=yesno
                                )
                            self._other_json = other_json
                            record["score"] = 0
                            self._state["similar"] = True
                            return

            await self.sender.sendMessage(
                'متاسفانه هیچ صدای مشابهی به صدای شما در حال حاضر در شبکه صوتی ما وجود ندارد. لطفاً در زمان دیگر امتحان کنید.'
            )
            if self._param['feedback']:
                self.scheduler.event_later(3,('_getFeedback', {'seconds': 3}))
            else:
                await self.tryAgain()
            return

    async def on__getFeedback(self, event):
        await self.sender.sendSticker(
            "CAADBAADbAEAAimanQW9ZbVDtmzeCgI"
        )
        await self.sender.sendMessage(
            "گفتن نظر خود 😊:",
            reply_markup=feedbackKeyboard
        )
        # self._state["comment"] = True
        return

    async def tryAgain(self):
        await self.sender.sendMessage(
            "دوباره تلاش کنیم؟",
            reply_markup=yesno
        )
        self._try = 3
        self._category = ''
        self._state = {"comment": False, "diff": False, "similar": False, "consent": False, "send_reply": False, 'send_voice': False}
        self._owner = True
        self._retry = True

class Main(telepot.aio.DelegatorBot):
    def __init__(self, token, owner_id, editor_id):
        if os.path.exists(CONSENTPATH):
            with open(CONSENTPATH, 'rb') as fid:
                self._consent = pickle.load(fid)
        else:
            self._consent = set()

        if os.path.exists(JSONPATH):
            with open(JSONPATH, 'rb') as fid:
                self._info = pickle.load(fid)
        else:
            self._info = {}

        self._store = UnreadStore()
        self._feedback = FeedbackStore()

        super(Main, self).__init__(token, [
            # Here is a delegate to specially handle owner commands.
            pave_event_space()(
                per_chat_id_in(owner_id, types=['private']),
                create_open,
                OwnerHandler,
                self._store,
                self._info,
                self._feedback,
                timeout=5000000
            ),

            pave_event_space()(
                per_chat_id_in(editor_id, types=['private']),
                create_open,
                EditorHandler,
                self._info,
                timeout=5000000
            ),
            include_callback_query_chat_id(pave_event_space())(
                per_chat_id_except(editor_id, types=['private',]),
                create_open,
                Mashahir,
                self._store,
                self._info,
                self._feedback,
                self._consent,
                timeout=5000000
            ),

            # Only one MessageSaver is ever spawned for entire application.
            (
                per_application(),
                create_open(MessageSaver, self._store, self._info, self._feedback, self._consent, exclude=owner_id)
            ),
        ])

# curl -F 'url=https://185.73.113.126:8443/abc'  -F 'certificate=selfPublic.pem'  https://api.telegram.org/bot370144284:AAHI5Jb04q4jeMUiK05v9DQlnp0gt9CqKMM/setWebhook

url_main = 'https://95.38.21.180:5005'

TOKEN = '370144284:AAHI5Jb04q4jeMUiK05v9DQlnp0gt9CqKMM'
PORT = 8443
URL = 'https://185.73.113.126:8443/abc'
CERT = 'selfPublic.pem'
OWNER_ID = [109337123, 145155148]
EDITOR_ID = [192165856, 332727887]
GETFILEPATH = 'getTelegramFile.sh'
VOICEPATH = '/home/demo/Mashahir/voices/'
CHATDBPATH = '/home/demo/Mashahir/chatdb'
CONSENTPATH = '/home/demo/Mashahir/consent'
FEEDBACKPATH = '/home/demo/Mashahir/feedback'
RULESPATH = '/home/demo/Mashahir/rules'
WELCOMEPATH = '/home/demo/Mashahir/welcome'
WELCOMEBACKPATH = '/home/demo/Mashahir/welcomeback'
GOODBYEPATH = '/home/demo/Mashahir/goodbye'
JSONPATH = '/home/demo/Mashahir/list.json'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

save_time = 60  # in seconds, time interval to save records in disk

category_list = {
    'خوانندگان داخلی': 'singer_iran',
    'خوانندگان خارجی': 'singer',
    'هنرپیشگان': 'actor'
}
inv_category_list = {v: k for k, v in category_list.items()}

category = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='خوانندگان داخلی'),
            KeyboardButton(text='خوانندگان خارجی'),
        ],
        [
            KeyboardButton(text='هنرپیشگان'),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

validation_list = {
    7: 'صحیح، شمرده و رسا',
    6: 'صحیح و شمرده ولی ضعیف',
    5: 'صحیح و شمرده همراه با نویز',
    4: 'صحیح ولی سریع و پیوسته',
    3: 'کلمه آخر رو ناقص خونده',
    2: 'با لحن آواز یا غیرعادی',
    1: 'اشتباه خونده',
    0: 'صدایی نیست'
}

inv_validation_list = {v: k for k, v in validation_list.items()}

validation = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=validation_list[6]),
            KeyboardButton(text=validation_list[7]),
        ],
        [
            KeyboardButton(text=validation_list[4]),
            KeyboardButton(text=validation_list[5]),
        ],
        [
            KeyboardButton(text=validation_list[2]),
            KeyboardButton(text=validation_list[3]),
        ],
        [
            KeyboardButton(text=validation_list[0]),
            KeyboardButton(text=validation_list[1]),
        ]
        
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

voiceValidation_list = {
    5: 'صدا واضح و مناسبیه',
    4: 'صدا خوبه ولی محیط نویز داره',
    3: 'صدای واضحی نیست یا نویز خیلی زیاده',
    0: 'صدایی نیست یا کلاً نویزه'
}
inv_voiceValidation_list = {v: k for k, v in voiceValidation_list.items()}

voiceValidation = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=voiceValidation_list[4]),
            KeyboardButton(text=voiceValidation_list[5]),
        ],
        [
            KeyboardButton(text=voiceValidation_list[0]),
            KeyboardButton(text=voiceValidation_list[3]),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

confirmation = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='موافقم 👍'),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

yesno = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='بلی'),
            KeyboardButton(text='خیر')
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

feedbackKeyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='خیلی باحاله ❤️', callback_data='5'),
        ],
        [
            InlineKeyboardButton(text='خوشم آمد 👍', callback_data='4'),
            InlineKeyboardButton(text='جالب بود 😲', callback_data='3')
        ],
        [
            InlineKeyboardButton(text='زیاد جالب نبود 😐', callback_data='2'),
            InlineKeyboardButton(text='اصلاً خوشم نیومد ☹️', callback_data='1')
        ]
    ]
)

bot = Main(TOKEN, OWNER_ID, EDITOR_ID)
update_queue = asyncio.Queue()  # channel between web app and bot


async def webhook(request):
    data = await request.text()
    await update_queue.put(data)  # pass update to bot
    return web.Response(body='OK'.encode('utf-8'))


async def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/abc', webhook)
    app.router.add_route('POST', '/abc', webhook)

    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    server_ctx.load_cert_chain(
        certfile='selfPublic.pem',
        keyfile='selfPrivate.key'
    )
    server_ctx.set_ciphers('ECDH+AESGCM')

    srv = await loop.create_server(
        app.make_handler(),
        host='0.0.0.0',
        port=PORT,
        ssl=server_ctx
    )
    print("Server started ...")

    await bot.setWebhook(
        url=URL,
        certificate=open(CERT, 'r'),
        max_connections=None,
        allowed_updates=None
    )

    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
# take updates from queue
loop.create_task(bot.message_loop(source=update_queue, ordered=True, maxhold=3))
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
