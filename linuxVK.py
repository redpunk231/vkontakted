#!/usr/bin/python2
# -*- coding: utf-8 -*-

import vk
import os
import dbus
import dbus.service
import time
import ConfigParser
import requests
import sqlite3

from vk import VkAuthorizationError
from requests import exceptions
from multiprocessing import Process, Queue

BUS_NAME='ru.linuxVK'
PATH='/linuxvk'
IFACE='ru.linuxVK.api'
CONFIG='linuxVK.conf'
CACHE_PATH  = '/.cache/vk-cli/'
DB_PATH     = ''
DB_NAME     = 'users.db'

token=''

def tryFunc(fn):
    def wrapped(*args, **kwargs):
        try:
            return (fn(*args, **kwargs))
        except (exceptions.SSLError, exceptions.Timeout, exceptions.ConnectionError, VkAuthorizationError, exceptions.HTTPError, ValueError), error:
            print error
            #time.sleep(1)
        return False
    return wrapped

@tryFunc
def apiAuthorization(login, passw):
    global token
    api = vk.API(app_id='4404997', user_login=login, user_password=passw, scope='notify,friends,messages,audio', api_version='5.21', timeout= 30)
    token = api.access_token
    return True

@tryFunc
def apiGetLongPollServer():
    vkapi = vk.API(access_token=token)
    return (vkapi('messages.getLongPollServer' ,use_ssl='0', need_pts='1'))

@tryFunc
def apiGetUserInfo(users):
    vkapi = vk.API(access_token=token)
    return (vkapi('users.get', user_ids=users, fields='photo_50'))

@tryFunc
def apiGetChat(chatIdValue):
    vkapi = vk.API(access_token=token)
    rez = vkapi('messages.getChat', chat_id=chatIdValue)
    return rez['title']

@tryFunc
def apiGetFrends():
    vkapi = vk.API(access_token=token)
    return (vkapi('friends.get', order='hints', fields='photo_50'))

@tryFunc
def apiSengMessage(msg, userId, chatId):
    vkapi = vk.API(access_token=token)
    if userId == 0:
        return (vkapi('messages.send', chat_id = chatId, message=msg))
    else:
        return (vkapi('messages.send', user_id=userId, message=msg))

@tryFunc
def apiGetLastDialogs():
    vkapi = vk.API(access_token=token)

    request = '\
        var result = [];\
        var count=50;\
        var dialogs = API.messages.getDialogs({"count":count});\
        var i = 0;\
        while (i < count) {\
            var local=[];\
            if (parseInt(dialogs.items[i].unread) != 0) {\
                if (parseInt(dialogs.items[i].message.chat_id) != 0){\
                    local = API.messages.getHistory({"count":dialogs.items[i].unread, "chat_id":dialogs.items[i].message.chat_id}).items;\
                }\
                else {\
                    local = API.messages.getHistory({"count":dialogs.items[i].unread, "user_id":dialogs.items[i].message.user_id}).items;\
                }\
            }\
            else {local = [dialogs.items[i].message];}\
            result = result + local;\
            i=i+1;\
        }\
        return  result;'

    return (vkapi('execute', code=request))


@tryFunc
def apiGetHistory(userId, countVal):
    vkapi = vk.API(access_token=token)
    return (vkapi('messages.getHistory', user_id=userId, count=countVal))

@tryFunc
def apiGetOnlineUsers():
    vkapi = vk.API(access_token=token)
    return (vkapi('friends.getOnline'))

@tryFunc
def apiMakeAsRead(idArray):
    vkapi = vk.API(access_token=token)
    vkapi('messages.markAsRead', message_ids=idArray)

@tryFunc
def requestLongPollServer(urlParts, ts = ""):
    if ts == "":
        url = u'http://' + urlParts['server'] + u'?act=a_check&key=' + urlParts['key'] + u'&ts=' + '%d' % urlParts['ts'] + u'&wait=5&mode=2'
    else:
        url = u'http://' + urlParts['server'] + u'?act=a_check&key=' + urlParts['key'] + u'&ts=' + ts + u'&wait=5&mode=2'

    response = requests.get(url, timeout=30)
    return vk.api.json.loads(response.content)

class dataBaseWrapper():
    def __init__(self):
        self.__home = os.getenv("HOME")
        DB_PATH = self.__home + CACHE_PATH

        if not (os.path.exists(self.__home + CACHE_PATH)):
            makedirs(self.__home + CACHE_PATH)

        self.__conn = sqlite3.connect(DB_PATH + DB_NAME, timeout=10)
        self.__cursor = self.__conn.cursor()

        self.__cursor.execute( 'CREATE TABLE IF NOT EXISTS users \
                    (\
                        id          INT     PRIMARY KEY     NOT NULL,\
                        name        TEXT                    NOT NULL,\
                        last_name   TEXT                    NOT NULL,\
                        photo_url   TEXT                    NOT NULL,\
                        online      INT                     NOT NULL \
                    )'
                )

        self.__cursor.execute( ' CREATE TABLE IF NOT EXISTS lastmsgs \
                    (\
                        id          INT     PRIMARY KEY     NOT NULL,\
                        user_id     INT                     NOT NULL,\
                        chat_id     INT                     NOT NULL,\
                        date        INT                     NOT NULL,\
                        isread      INT                     NOT NULL,\
                        out         INT                     NOT NULL \
                    )'
                )

        self.__cursor.execute( ' CREATE TABLE IF NOT EXISTS chats \
                    (\
                        id          INT     PRIMARY KEY     NOT NULL,\
                        title       TEXT                    NOT NULL\
                    )' 
                )

    def __del__(self):
        self.__conn.close()

    def UpdateDB(self):
        listId=u''
        peoples=None
        for k in (self.__cursor.execute( 'SELECT id FROM users' )):
            listId+='%d,'%k[0]
        if listId != u'':
            listId.replace(listId[-1],'')
            peoples = apiGetUserInfo(listId)
        else:
            items = apiGetFrends()
            peoples = items['items']

        for q in peoples:
            user = self.__getUserInfoFromDB(q['id'])
            need_photo = False
            if not user:
                self.__cursor.execute( 'INSERT INTO users VALUES(?, ?, ?, ?, ?)', (q['id'], q['first_name'], q['last_name'], q['photo_50'], 0) )
                self.__conn.commit()
            elif user[3] != q['photo_50']:
                    self.__cursor.execute( ' UPDATE users SET photo_url = ? WHERE id = ? ', (q['photo_50'], q['id']) )
                    self.__conn.commit()
                    need_photo = True

            if not (os.path.exists(self.__home + CACHE_PATH + '%d.jpg'%q['id'])):
                need_photo = True

            if need_photo:
                self.__download_file(q['photo_50'], q['id'])

        print 'Data Base updated'

    def getUserInfo(self, userId):
        data = self.__getUserInfoFromDB(userId)
        if data == None:
            self.__getUserInfoFromVK(userId)
            data = self.__getUserInfoFromDB(userId)
        return data

    def __getUserInfoFromDB(self, user_id):
        self.__cursor.execute( 'SELECT * FROM users WHERE id=%d'%user_id )
        return (self.__cursor.fetchone())

    def __getUserInfoFromVK(self, user_id):
        userData = apiGetUserInfo(user_id);

        self.__cursor.execute( 'INSERT INTO users VALUES(?, ?, ?, ?, ?)', (userData[0]['id'], userData[0]['first_name'],userData[0]['last_name'],userData[0]['photo_50'], 0) )
        self.__conn.commit()

        self.__download_file(userData[0]['photo_50'], userData[0]['id'])

    def __download_file(self, url, userId):
        filename = self.__home + CACHE_PATH + '%d.jpg' % userId
        if (os.path.exists(filename)):
            os.remove(filename)
        r = requests.get(url, stream=True)
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024): 
                if chunk: 
                    f.write(chunk)
                    f.flush()

    def getOnlineUsers(self):
        self.__cursor.execute( ' UPDATE users SET online = 0 ' )
        for q in apiGetOnlineUsers():
            self.__cursor.execute( ' UPDATE users SET online = ? WHERE id = ? ', (1, q) )
        self.__conn.commit()

    def getLastDialogsFromVK(self):
        self.__cursor.execute( 'DELETE FROM lastmsgs' )
        self.__conn.commit()

        response = apiGetLastDialogs()

        for msg in response:
            if 'chat_id' not in msg.keys():
                chat_id = 0
            else:
                chat_id = msg['chat_id']
            self.__cursor.execute( ' INSERT INTO lastmsgs VALUES(?, ?, ?, ?, ?, ?) ', (msg['id'], msg['user_id'], chat_id, msg['date'], msg['read_state'], msg['out']) )
        self.__conn.commit()


    def getLastDialogsFromDB(self):
        data = self.__cursor.execute ( '\
            select a.title from (\
	        select (u.name||" "||u.last_name) as title, lm.date from users as u, lastmsgs as lm where u.id=lm.user_id and lm.chat_id=0\
	        union\
	        select c.title, lm.date from chats as c, lastmsgs as lm where c.id=lm.chat_id\
            ) a order by date desc\
        ' )
        longStr = []
        for d in data:
            if d[0] not in longStr:
                longStr.append(u'%s' % d[0])
        return (u'\n'.join(longStr))

    def findUserInDb(self, title):
        data = self.__cursor.execute( ' select distinct id from (\
                    select (u.name||" "||u.last_name) as full_name, u.id from users as u\
                ) a where full_name="%s" ' % title )

        for d in data:
            return d[0]
        return 0

    def findChatInDB(self, title):
        data = self.__cursor.execute( ' select distinct id from chats where title="%s" ' % title )
        for d in data:
            return d[0]
        return 0

    def msgToDB(self, msgId, userId, chat_id, date, isread, out):
        self.__cursor.execute( 'INSERT INTO lastmsgs VALUES(?, ?, ?, ?, ?, ?)', (msgId, userId, chat_id, date, isread, out))
        self.__conn.commit()

    def makeMessageAsReadIdDB(self, msgId):
        self.__cursor.execute( ' UPDATE lastmsgs SET isread = ? WHERE id = ? ', (1, msgId) )
        self.__conn.commit()


    def getChatTitle(self, chat_id):
        self.__cursor.execute( 'SELECT title FROM chats WHERE id=%d' % chat_id )
        data = self.__cursor.fetchone()
        if data == None:
            rezult = apiGetChat(chat_id)
            self.__cursor.execute( ' INSERT INTO chats VALUES(?,?) ', (chat_id, rezult) )
            self.__conn.commit()
        else:
            rezult = data[0]
        return rezult

class apiWrapper(dbus.service.Object):
    def __init__(self, bus):
        super(apiWrapper, self).__init__(bus, PATH)
        print "Running dbus service."

        config = ConfigParser.RawConfigParser()
        config.read(os.getenv('HOME') + '/.config/' + CONFIG)
        login = config.get('AUTH_DATA', 'login')
        passw = config.get('AUTH_DATA', 'passw')
        self.__countTry = config.get('APP_SETTINGS', 'count-of-try')
        self.__breakTime = config.get('APP_SETTINGS', 'break-time')

        self.__db = dataBaseWrapper()

        self.__queueCommands = Queue()
        self.__queueCommands.put([u'init'])  # Just need

        if (self.Authorization(login, passw)):
            self.__db.UpdateDB()
            self.__db.getOnlineUsers()
            self.__db.getLastDialogsFromVK()
            print "Command wait..."

    def __processingResponse(self, masResp):
        if masResp == []: return
        for elem in masResp:
            if elem[0] == 4:
                flags = (self.__getFlags(elem[2]))
                chat_id = 0
                user_id = elem[3]
                out = 1
                if "MULTIDIALOG" in flags:
                    chat_id = elem[3]-2000000000
                    user_id = int (elem[7]['from'])

                if "OUTBOX" not in flags:
                    out = 0
                    self.notifySend(elem[6], user_id, chat_id)
                        
                self.__db.msgToDB(elem[1], user_id, chat_id, elem[4], out, out)
            if elem[0] == 3:
                self.__db.makeMessageAsReadIdDB(elem[1])

            if elem[0] == 8: # user online
                pass
                #self.changeUserPresence(0 - elem[1], 1)

            if elem[0] == 9: #user offline
                pass
                #self.changeUserPresence(0 - elem[1], 0)

    def __getFlags(self, mask):
        flags = []
        if mask >= 8192:flags.append("MULTIDIALOG");mask -= 8192
        if mask >= 512: flags.append("MEDIA");      mask -= 512
        if mask >= 256: flags.append("FIXED");      mask -= 256
        if mask >= 128: flags.append("DELETED");    mask -= 128
        if mask >= 64:  flags.append("SPAM");       mask -= 64
        if mask >= 32:  flags.append("FRIENDS");    mask -= 32
        if mask >= 16:  flags.append("CHAT");       mask -= 16
        if mask >= 8:   flags.append("IMPORTANT");  mask -= 8
        if mask >= 4:   flags.append("REPLIED");    mask -= 4
        if mask >= 2:   flags.append("OUTBOX");     mask -= 2
        if mask == 1:   flags.append("UNREAD")
        return flags

    def notifySend(self, message, user_id, chat_id=0):
        userInfo = self.__db.getUserInfo(user_id)
        if chat_id == 0:
            title = '%s %s' % (userInfo[1], userInfo[2])
        else:
            title = self.__db.getChatTitle(chat_id)
        image = (os.getenv('HOME') + CACHE_PATH + '%d.jpg'%userInfo[0])
        
        self.Notify(title, message, image)

    def __longPollProccess(self):
        ts=""
        longPollResponse = apiGetLongPollServer()
        while True:
            response = requestLongPollServer(longPollResponse,ts)
            if response != False:
                if 'failed' in response:
                    longPollResponse = apiGetLongPollServer()
                    ts=""
                else: 
                    self.__processingResponse(response['updates'])
                    ts = "%s" % response['ts']
            else:
                time.sleep(1)
    
    def __cmdQueueProccess(self):
        while True:
            cmdResult = False
            i = 0
            maxTry = 5
            cmd = self.__queueCommands.get()

            while (cmdResult == False): 
                if cmd[0] == u'init':
                    print "Command queue inited"
                    cmdResult = True
                if cmd[0] == u'SendMessage':
                    cmdResult = apiSengMessage(cmd[1][0], cmd[1][1], cmd[1][2])
                    #apiMakeAsRead

                i+=1;
                if i >= int(self.__countTry):
                    break
                time.sleep(int (self.__breakTime))

            if cmdResult == False:
                self.Notify(u'Ошибка соединения', u'',u'/home/redpunk/.config/awesome/Error.png')
                while not (self.__queueCommands.empty()):
                    self.__queueCommands.get()

    def startLongPoolProccess(self):
        self.__lpProccess = Process(target=self.__longPollProccess)
        self.__lpProccess.start()
       
        #time.sleep(5)
        self.__queueProccess = Process(target=self.__cmdQueueProccess)
        self.__queueProccess.start()

    @dbus.service.method(IFACE, in_signature='ss', out_signature='b')
    def Authorization(self, login, passw):
        self.__login = login
        self.__passw = passw
        auth = apiAuthorization(login, passw)
        if auth != False:
            print "Success auth"
            self.startLongPoolProccess()
            return True
        else:
            print "Error auth"
            return False

    @dbus.service.method(IFACE, in_signature='', out_signature='s')
    def GetLastDialogs(self):
        return (self.__db.getLastDialogsFromDB())

    @dbus.service.method(IFACE, in_signature='ss', out_signature='')
    def SendMsg(self, title, msg):
        user_id=self.__db.findUserInDb(title)
        chat_id=self.__db.findChatInDB(title)
        #apiSengMessage(msg, user_id, chat_id)
        #self.__queueCommands.put([apiSengMessage, [msg, user_id, chat_id]])
        self.__queueCommands.put([u'SendMessage', [u'%s' % msg, user_id, chat_id]])

    @dbus.service.signal(IFACE)
    def Notify(self, title, body, icon):
        pass



if __name__ == '__main__':
    import gobject
    import dbus.mainloop.glib
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    session_bus = dbus.SessionBus()
    name = dbus.service.BusName(BUS_NAME, session_bus)
    api = apiWrapper(session_bus)

    mainloop = gobject.MainLoop()
    mainloop.run()
