#!/usr/bin/python2

import dbus
import os

BUS_NAME='ru.linuxVK'
PATH='/linuxvk'
IFACE='ru.linuxVK.api'

class VkApiCli():
    def __init__(self):
        flag = False

        bus = dbus.SessionBus()
        self.__obj = bus.get_object(bus_name = BUS_NAME, object_path = PATH)

    def auth(self, login, passw):
        method = self.__obj.get_dbus_method('Authorization', IFACE)

    def send(self, msg, user_id, chat_id):
        method = self.__obj.get_dbus_method('SendMsg', IFACE)
        method(msg, user_id, chat_id)

 
    def getChatTitle(self, chat_id):
        rezult='test'
        self.__cursor.execute( 'SELECT title FROM chats WHERE id=%d' % chat_id )
        data = self.__cursor.fetchone()
        if data == None:
            method = self.__obj.get_dbus_method('GetDialogInfo', IFACE)
            rezult = method(chat_id)
            self.__cursor.execute( ' INSERT INTO chats VALUES(?,?) ', (chat_id, rezult) )
            self.__conn.commit()
        else:
            rezult = data[0]
        return rezult

    def notify(self, summary, body='', app_name='', app_icon='', timeout=5000, actions=[], hints=[], replaces_id=0):
        _bus_name = 'org.freedesktop.Notifications'
        _object_path = '/org/freedesktop/Notifications'
        _interface_name = _bus_name

        session_bus = dbus.SessionBus()
        obj = session_bus.get_object(_bus_name, _object_path)
        interface = dbus.Interface(obj, _interface_name)
        interface.Notify(app_name, replaces_id, app_icon,
                summary, body, actions, hints, timeout)

        #self.getCountUnreadedMsg()

    def getCountUnreadedMsg(self):
        self.__cursor.execute( 'SELECT COUNT(isread) FROM lastmsgs WHERE isread=0' )
        unread_count = self.__cursor.fetchone()
        if unread_count[0]!=0:
            os.system('echo \"testw:set_markup(\' %d \')\" | awesome-client' % unread_count[0])
        else:
            os.system('echo \"testw:set_markup(\'\')\" | awesome-client')

    def messageIsRead(self, msgId):
        self.__cursor.execute( ' UPDATE lastmsgs SET isread = ? WHERE id = ? ', (1, msgId) )
        self.__conn.commit()

    def getOnlineUsers(self):
        self.__cursor.execute( ' UPDATE users SET online = 0 ' )
        method = self.__obj.get_dbus_method('GetOnlineUsers', IFACE)
        #users = method()
        for q in method():
            self.__cursor.execute( ' UPDATE users SET online = ? WHERE id = ? ', (1, q) )
        self.__conn.commit()

    def changeUserStatus(self, userId, status):
        self.__cursor.execute( ' UPDATE users SET online = ? WHERE id = ? ', (status, userId) )
        self.__conn.commit()

    def findUserInDb(self, title):
        data = self.__cursor.execute( ' select distinct id from (\
                    select (u.name||" "||u.last_name) as full_name, u.id from users as u\
                ) a where full_name="%s" ' % title )

        for d in data:
            return d[0]
        return None

    def findChatInDB(self, title):
        data = self.__cursor.execute( ' select distinct id from chats where title="%s" ' % title )
        for d in data:
            return d[0]
        return None

    def markAsReadDialog(self, id_value):
        data = self.__cursor.execute( ' select id from lastmsgs where user_id=%d and isread=0 ' % id_value )
        ids=[]
        for d in data:
            #print d[0]
            ids.append(u'%d' % d[0]) 
        if len(ids) != 0:
            method = self.__obj.get_dbus_method('MakeMsgAsRead', IFACE)
            q = u','.join(ids)
            method(q)



if __name__ == '__main__':
    import argparse
    import sys
    import commands

    parser = argparse.ArgumentParser()

    parser.add_argument('--auth' ,          action='store_true',    dest='auth',        help='Auth',            default=False       )
    parser.add_argument('--send-msg' ,      action='store_true',    dest='sendMsg',     help='Sent to user',    default=False       )
    parser.add_argument('--notify' ,        action='store_true',    dest='notify',      help='Notify',          default=False       )
    parser.add_argument('--control',        action='store_true',    dest='control',                             default=False       )

    parser.add_argument('-l', '--login',    action='store',         dest='login',                                                   )
    parser.add_argument('-p', '--passw',    action='store',         dest='passw',                                                   )

    parser.add_argument('-t', '--title',    action='store',         dest='title',                                                   )
    parser.add_argument('-b', '--body',     action='store',         dest='body',                                                    )
    parser.add_argument('-i', '--icon',     action='store',         dest='icon',                                                    )

    parser.add_argument('-v', '--version',  action='version',       version='%(prog)s 0.1'                                          )

    results = parser.parse_args()

    api = VkApiCli()

    if results.auth: 
        api.auth(results.login, results.passw)

    elif results.notify:
        api.notify(summary = results.title, body = results.body, app_icon = results.icon)

    elif results.sendMsg:
        bus = dbus.SessionBus()
        obj = bus.get_object(bus_name = BUS_NAME, object_path = PATH)
        method = obj.get_dbus_method('GetLastDialogs', IFACE)
        dialog_titles = method()

        cmd = u'echo "%s" | dmenu -nf "#C8BBB8" -nb "#252525" -sb "#353535" -fn "Sony Sketch EF-11" -b 2>/dev/null' % dialog_titles
        title = commands.getoutput(cmd.encode("utf-8"))
        
        if title != '':
            get_message = r'cat /dev/null | dmenu -nf "#C8BBB8" -nb "#252525" -sb "#353535" -fn "Sony Sketch EF-11" -b -p "%s" 2>/dev/null' % title
            message = commands.getoutput(get_message)
            if message != '':
                method = obj.get_dbus_method('SendMsg', IFACE)
                method(title, message)

    elif results.control:
        cmd = 'echo "Online\nOffline\nMask as read all msg" | dmenu -nf "#C8BBB8" -nb "#252525" -sb "#353535" -fn "Sony Sketch EF-11" -b -p "Do" 2>/dev/null'
        title = commands.getoutput(cmd)
        if title != '':
            if title == 'Online':
                api.auth('slipry@mail.ru', 'coeqepwe9107736097')
            elif title == 'Offline':
                pass
            elif title == 'Mask as read all msg':
                pass
