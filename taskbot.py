import json
import requests
import time
import urllib
import sqlalchemy
import string
import os

import db
from db import Task

HELP = """
 /new NOME, NOME...
 /todo ID, ID...
 /doing ID, ID...
 /done ID, ID...
 /delete ID, ID...
 /list
 /rename ID NOME
 /dependson ID ID...
 /duplicate ID
 /priority ID PRIORITY{low, medium, high}
 /listpriority
 /duedate ID DUEDATE{dd/mm/yyyy}
 /help
"""
tokenFile = "botToken.txt"
loginData = "loginData.txt"


def readTokenFile():
    """Read the bot token."""
    inputFile = open(tokenFile, 'r')
    getToken = inputFile.readline()
    getToken = getToken.rstrip('\n')
    return getToken


botURL = "https://api.telegram.org/bot{}/".format(readTokenFile())


def get_url(url):
    """Get the bot url."""
    response = requests.get(url)
    content = response.content.decode("utf8")
    return content


def split_message(msg):
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]
    return msg, text


def get_json_from_url(url):
    """Get the json from url."""
    content = get_url(url)
    js = json.loads(content)
    return js


def get_updates(offset=None):
    """Get the updates fom url."""
    url = botURL + "getUpdates?timeout=100"
    if offset:
        url += "&offset={}".format(offset)
    js = get_json_from_url(url)
    return js


def send_message(text, chat_id, reply_markup=None):
    """Send message to user in chat."""
    text = urllib.parse.quote_plus(text)
    url = botURL + "sendMessage?text={}&chat_id={}&parse_mode=Markdown".format(text, chat_id)
    if reply_markup:
        url += "&reply_markup={}".format(reply_markup)
    get_url(url)


def get_last_update_id(updates):
    """Get the id of the last update."""
    update_ids = []
    for update in updates["result"]:
        update_ids.append(int(update["update_id"]))

    return max(update_ids)


def deps_text(task, chat, preceed=''):
    """Put the icon."""
    text = ''

    for i in range(len(task.dependencies.split(',')[:-1])):
        line = preceed
        query = db.session.query(Task).filter_by(id=int(task.dependencies.split(',')[:-1][i]), chat=chat)
        dep = query.one()

        icon = '\U0001F195'
        if dep.status == 'DOING':
            icon = '\U000023FA'
        elif dep.status == 'DONE':
            icon = '\U00002611'

        if i + 1 == len(task.dependencies.split(',')[:-1]):
            line += '└── [[{}]] {} {}\n'.format(dep.id, icon, dep.name)
            line += deps_text(dep, chat, preceed + '    ')
        else:
            line += '├── [[{}]] {} {}\n'.format(dep.id, icon, dep.name)
            line += deps_text(dep, chat, preceed + '│   ')

        text += line

    return text


def getLoginData():
    """Get the data to do login on git."""
    inputFile = open(loginData, 'r')
    getLoginData = inputFile.read().split('\n')
    return getLoginData


def createIssueGitHub(msg, chat):
    """Create the issue on gitHub."""
    taskList = msg.split(',')
    for task in taskList:
        gitOwner = 'TecProg-20181'
        gitName = 'T--jarbas_bot'
        repoUrl = 'https://api.github.com/repos/%s/%s/issues' % (gitOwner, gitName)

        sessionGitHub = requests.Session()
        loginData = getLoginData()
        sessionGitHub.auth = (loginData[0], loginData[1])

        issueTitle = task
        newIssue = {'title': issueTitle}

        postIssue = sessionGitHub.post(repoUrl, json.dumps(newIssue))
        if postIssue.status_code == 201:
            send_message('*The issue _{0:s}_ was created on Github*'.format(issueTitle), chat)
        else:
            send_message('*Sorry! The issue _*{0:s}*_ could not be created on GitHub'.format(issueTitle), chat)


def newTask(msg, chat):
    taskList = msg.split(',')
    print('msg:{} chat:{} list:{}'.format(msg, chat, taskList))#Debug
    for task in taskList:
        task = task.strip()
        task = Task(chat=chat, name=task, status='TODO', dependencies='', parents='', priority='', duedate=None)
        db.session.add(task)
        db.session.commit()
        send_message("New task *TODO* [[{}]] {}".format(task.id, task.name), chat)

def deleteTask(msg, chat):
    """Delete a task."""
    taskList = msg.split(',')
    for task in taskList:
        task = task.strip()
        if not task.isdigit():
            send_message("You must inform the tasks ids", chat)
        else:
            taskId = int(task)
            taskQuery = db.session.query(Task).filter_by(id=taskId, chat=chat)
            try:
                taskFound = taskQuery.one()
            except sqlalchemy.orm.exc.NoResultFound:
                send_message("_404_ Task {} not found x.x".format(taskId), chat)
                return
            for dependentTask in taskFound.dependencies.split(',')[:-1]:
                dependentQuery = db.session.query(Task).filter_by(id=int(dependentTask), chat=chat)
                try:
                    dependentTask = dependentQuery.one()
                    dependentTask.parents = dependentTask.parents.replace('{},'.format(taskFound.id), '')
                except sqlalchemy.orm.exc.NoResultFound:
                    print("Dependent task {} already deleted, continue...".format(dependentTask))
            db.session.delete(taskFound)
            db.session.commit()
            send_message("Task [[{}]] deleted".format(taskId), chat)


def listPriority(chat):
    """List the tasks priorities."""
    list_text = ''

    list_text += '❗ Priority List\n'
    list_text += 'No Priority:\n'
    query = db.session.query(Task).filter_by(priority='', chat=chat).order_by(Task.id)
    for task in query.all():
        list_text += '[[{}]] {}\n'.format(task.id, task.name)
    list_text += 'High Priority:\n'
    query = db.session.query(Task).filter_by(priority='--> HIGH', chat=chat).order_by(Task.id)
    for task in query.all():
        list_text += '[[{}]] {}\n'.format(task.id, task.name)
    list_text += 'Medium Priority:\n'
    query = db.session.query(Task).filter_by(priority='--> MEDIUM', chat=chat).order_by(Task.id)
    for task in query.all():
        list_text += '[[{}]] {}\n'.format(task.id, task.name)
    list_text += 'Low Priority:\n'
    query = db.session.query(Task).filter_by(priority='--> LOW', chat=chat).order_by(Task.id)
    for task in query.all():
        list_text += '[[{}]] {}\n'.format(task.id, task.name)

    send_message(list_text, chat)


def renameTask(msg, chat):
    """Rename a task."""
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]

    if not msg.isdigit():
        send_message("You must inform the task id", chat)
    else:
        task_id = int(msg)
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        if text == '':
            send_message(
                "You want to modify task {}, but you didn't provide anynew text".format(task_id), chat)
            return

        old_text = task.name
        task.name = text
        db.session.commit()
        send_message("Task {} redefined from {} to {}".format(task_id, old_text, text), chat)


def duplicateTask(msg, chat):
    """Copy and past a task."""
    if not msg.isdigit():
        send_message("You must inform the task id", chat)
    else:
        task_id = int(msg)
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        duplicatedTask = Task(chat=task.chat, name=task.name,
                              status=task.status, dependencies=task.dependencies,
                              parents=task.parents, priority=task.priority,
                              duedate=task.duedate)
        db.session.add(duplicatedTask)

        for taskN in task.dependencies.split(',')[:-1]:
            query = db.session.query(Task).filter_by(id=int(taskN), chat=chat)
            taskN = query.one()
            taskN.parents += '{},'.format(duplicatedTask.id)

        db.session.commit()
        send_message("New task *TODO* [[{}]] {}".format(duplicatedTask.id, duplicatedTask.name), chat)


def setTaskStatus(msg, chat, status):
    """Set a status to the task."""
    taskList = msg.split(',')
    for task in taskList:
        task = task.strip()
        if not task.isdigit():
            send_message("You must inform the task ids", chat)
        else:
            task_id = int(task)
            query = db.session.query(Task).filter_by(id=task_id, chat=chat)
            try:
                taskFound = query.one()
            except sqlalchemy.orm.exc.NoResultFound:
                send_message("_404_ Task {} not found x.x".format(task_id), chat)
                return
            if status == 'DONE':
                taskFound.status = 'DONE'
            elif status == 'DOING':
                taskFound.status = 'DOING'
            elif status == 'TODO':
                taskFound.status = 'TODO'
            db.session.commit()
            send_message("*{}* task [[{}]] {}".format(status, taskFound.id, taskFound.name), chat)


def listTask(chat):
    """List the tasks in the database."""
    responseMessage = ''

    responseMessage += '\U0001F4CB Task List\n'
    query = db.session.query(Task).filter_by(parents='', chat=chat).order_by(Task.id)
    for task in query.all():
        icon = '\U0001F195'
        if task.status == 'DOING':
            icon = '\U000023FA'
        elif task.status == 'DONE':
            icon = '\U00002611'

        responseMessage += '[[{}]] {} {}\n *Due Date: {}*\n\n'.format(task.id, icon, task.name, task.duedate)
        responseMessage += deps_text(task, chat)

    send_message(responseMessage, chat)
    responseMessage = ''

    responseMessage += '\U0001F4DD _Status_\n'
    query = db.session.query(Task).filter_by(status='TODO', chat=chat).order_by(Task.id)
    responseMessage += '\n\U0001F195 *TODO*\n'
    for task in query.all():
        responseMessage += '[[{}]] {}\n'.format(task.id, task.name)
    query = db.session.query(Task).filter_by(status='DOING', chat=chat).order_by(Task.id)
    responseMessage += '\n\U000023FA *DOING*\n'
    for task in query.all():
        responseMessage += '[[{}]] {}\n'.format(task.id, task.name)
    query = db.session.query(Task).filter_by(status='DONE', chat=chat).order_by(Task.id)
    responseMessage += '\n\U00002611 *DONE*\n'
    for task in query.all():
        responseMessage += '[[{}]] {}\n'.format(task.id, task.name)

    send_message(responseMessage, chat)


def showDependsOn(msg, chat):
    """Show the tasks dependencies."""
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]

    if not msg.isdigit():
        send_message("You must inform the task id", chat)
    else:
        task_id = int(msg)
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        if text == '':
            for dependentTask in task.dependencies.split(',')[:-1]:
                dependentTask = int(dependentTask)
                query = db.session.query(Task).filter_by(id=dependentTask, chat=chat)
                taskFound = query.one()
                taskFound.parents = taskFound.parents.replace('{},'.format(task.id), '')

            task.dependencies = ''
            send_message("Dependencies removed from task {}".format(task_id), chat)
        elif circularDependency(text, task_id):
            send_message("Task {} already depends on {}".format(text, task_id), chat)
            return
        else:
            for depid in text.split(' '):
                if not depid.isdigit():
                    send_message("All dependencies ids must be numeric, and not {}".format(depid), chat)
                else:
                    depid = int(depid)
                    query = db.session.query(Task).filter_by(id=depid, chat=chat)
                    try:
                        taskdep = query.one()
                        taskdep.parents += str(task.id) + ','
                    except sqlalchemy.orm.exc.NoResultFound:
                        send_message("_404_ Task {} not found x.x".format(depid), chat)
                        continue

                    deplist = task.dependencies.split(',')
                    if str(depid) not in deplist:
                        task.dependencies += str(depid) + ','

        db.session.commit()
        send_message("Task {} dependencies up to date".format(task_id), chat)


def circularDependency(taskId, dependentTaskId):
    """Verify tha circular dependency."""
    query = db.session.query(Task).filter_by(id=taskId)
    try:
        taskFound = query.one()
        taskDependenciesList = taskFound.dependencies.split(",")
    except sqlalchemy.orm.exc.NoResultFound:
        send_message("_404_ Task {} not found x.x".format(taskId), chat)
    if str(dependentTaskId) in taskDependenciesList:
        return True
    else:
        return False


def setTaskPriority(msg, chat):
        """Set task priority."""
        text = ''
        if msg != '':
            if len(msg.split(' ', 1)) > 1:
                text = msg.split(' ', 1)[1]
            msg = msg.split(' ', 1)[0]

        if not msg.isdigit():
            send_message("You must inform the task id", chat)
        else:
            task_id = int(msg)
            query = db.session.query(Task).filter_by(id=task_id, chat=chat)
            try:
                task = query.one()
            except sqlalchemy.orm.exc.NoResultFound:
                send_message("_404_ Task {} not found x.x".format(task_id), chat)
                return

            if text == '':
                task.priority = ''
                send_message("_Cleared_ all priorities from task {}".format(task_id), chat)
            else:
                if text.lower() not in ['high', 'medium', 'low']:
                    send_message("The priority *must be* one of the following: high, medium, low", chat)
                else:
                    task.priority = text.lower()
                    if text.lower() == 'high':
                        task.priority = "--> HIGH"

                    elif text.lower() == 'medium':
                        task.priority = "--> MEDIUM"

                    elif text.lower() == 'low':
                        task.priority = "--> LOW"

                    send_message("*Task {}* priority has priority *{}*".format(task_id, text.lower()), chat)
            db.session.commit()


def setDueDate(chat, msg):
    """Ser a due date to the task."""
    text = ''
    task = Task

    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]

    if not msg.isdigit():
        send_message("You have to inform the task id", chat)

    else:
        task_id = int(msg)
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)

        try:
            task = query.one()

        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)

    if text == '':
        task.duedate = ''
        send_message("_Cleared_ due date from task {}".format(task_id), chat)

    else:
        text = text.split("/")
        text.reverse()
    if not (1 <= int(text[2]) <= 31 and 1 <= int(text[1]) <= 12 and 1900 <= int(text[0]) <= 2100):
        send_message(
        "The due date format is: *DD/MM/YYYY* (Max number day = 31, Max mouth day = 12 and Max number year = 2100 ) )", chat)

    else:
        from datetime import datetime
        task.duedate = datetime.strptime(" ".join(text), '%Y %m %d')
        send_message(
         "Task {} has the due date *{}*".format(task_id, task.duedate), chat)

        db.session.commit()


def handle_updates(updates):
    """Control the bot menu."""
    for update in updates["result"]:
        if 'message' in update:
            message = update['message']
        elif 'edited_message' in update:
            message = update['edited_message']
        else:
            print('Can\'t process! {}'.format(update))
            return

        msg = ''
        if 'text' in message:
            command = message["text"].split(" ", 1)[0]
            if len(message["text"].split(" ", 1)) > 1:
                msg = message["text"].split(" ", 1)[1].strip()
        else:
            command = '/start'

        chat = message["chat"]["id"]

        print(command, msg, chat)

        if command == '/new':
            newTask(msg, chat)
            createIssueGitHub(msg, chat)

        elif command == '/rename':
            renameTask(msg, chat)

        elif command == '/duplicate':
            duplicateTask(msg, chat)

        elif command == '/delete':
            deleteTask(msg, chat)

        elif command == '/todo':
            setTaskStatus(msg, chat, 'TODO')

        elif command == '/doing':
            setTaskStatus(msg, chat, 'DOING')

        elif command == '/done':
            setTaskStatus(msg, chat, 'DONE')

        elif command == '/list':
            listTask(chat)

        elif command == '/dependson':
            showDependsOn(msg, chat)

        elif command == '/priority':
            setTaskPriority(msg, chat)

        elif command == '/listpriority':
            listPriority(chat)

        elif command == '/duedate':
            setDueDate(chat, msg)

        elif command == '/start':
            send_message("Welcome! Here is a list of things you can do.", chat)
            send_message(HELP, chat)

        elif command == '/help':
            send_message("Here is a list of things you can do.", chat)
            send_message(HELP, chat)
        else:
            send_message("I'm sorry dave. I'm afraid I can't do that.", chat)


def main():
    """Start the project."""
    last_update_id = None

    while True:
        print("Updates")
        updates = get_updates(last_update_id)

        if len(updates["result"]) > 0:
            last_update_id = get_last_update_id(updates) + 1
            handle_updates(updates)

        time.sleep(0.5)


if __name__ == '__main__':
    main()
