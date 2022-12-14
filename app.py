import json
from flask import Flask, request
from flask_cors import CORS, cross_origin
from datetime import date, datetime, timedelta
from calendar import monthrange
import locale
import base64

from mp3_tagger import MP3File, VERSION_1, VERSION_2, VERSION_BOTH
from os import environ
import cv2
from PIL import ImageFont, ImageDraw, Image
import numpy as np

import db

app = Flask(__name__)
CORS(app)


@app.route('/')
def hello():
    return 'Hello, World!'


@app.route('/getCurrentSong')
@cross_origin()
def getCurrentSong():
    folders = ['C:', 'Users', 'info', 'Documents', 'VirtualDJ', 'History']
    currDate = date.today()
    fileName = f"{currDate.year}-{currDate.month if currDate.month >= 10 else '0' + str(currDate.month)}-{currDate.day if currDate.day >= 10 else '0' + str(currDate.day)}"
    path = ''
    for folder in folders:
        path += folder + '\\'
    file = path + fileName + '.m3u'
    f = open(file, 'r', encoding='utf-8')
    song = f.readlines()[len(f.readlines()) - 1].split('\\')
    songfile = ""
    for folder in song:
        songfile += folder + '/'
    song = songfile[:-2]
    f.close()
    songTags = MP3File(song)
    return songTags.get_tags()["ID3TagV2"]


@app.route('/putCurrentSong', methods=['PUT'])
@cross_origin()
def putCurrentSong():
    song, artist = request.get_json()['song'], request.get_json()['artist']
    conn, cur = db.connect_db()
    cur.execute('''SELECT * FROM playedSongs
                WHERE datetime(playedSongs.played_at)
                BETWEEN datetime("now", "localtime", "-45 seconds")
                AND datetime("now", "localtime"); 
            ''')
    isInTime = cur.fetchone()
    cur.execute('''
        SELECT songs.title, artists.name
        FROM playedSongs
        INNER JOIN songs ON songs.song_id = playedSongs.song
        INNER JOIN artists ON artists.artist_id = songs.artist
        ORDER BY playedSongs.id DESC LIMIT 1
    ''')
    lastSong = cur.fetchone()
    lastSongBool = True
    if lastSong is not None:
        lastSongBool = not (lastSong["name"] == artist and lastSong["title"] == song)
    timeBool = isInTime is None
    if not timeBool:
        cur.execute('''DELETE FROM playedSongs WHERE played_at = ( select max(played_at) from playedSongs);''')
        conn.commit()
    if lastSongBool and artist != 'Eisb??r Metalkeller':
        cur.execute('SELECT artist_id from artists where name=?', (artist,))
        artist_id = cur.fetchone()
        if artist_id is None:
            cur.execute('INSERT INTO artists(name) VALUES (?)', (artist,))
            conn.commit()
            artist_id = cur.lastrowid
        else:
            artist_id = artist_id['artist_id']
        cur.execute('''SELECT song_id FROM songs
            INNER JOIN artists ON artists.artist_id=songs.artist
            WHERE artists.name=? AND songs.title=?
        ''', (artist, song))
        song_id = cur.fetchone()
        if song_id is None:
            cur.execute('''INSERT INTO songs (title, artist) VALUES (?, ?)''', (song, artist_id))
            conn.commit()
            song_id = cur.lastrowid
        else:
            song_id = song_id['song_id']
        currTime = datetime.now()
        cur.execute('''
            INSERT INTO playedSongs (played_at, song)
            VALUES (?, ?)
        ''', (currTime, song_id))
        conn.commit()
        print('was uploaded')
    else:
        if not lastSongBool:
            print('same song')
    cur.close()
    conn.close()
    return 'yo'


@app.route('/getAllPlayedSongs')
@cross_origin()
def getAllPlayedSongs():
    db.createTables()
    conn, cur = db.connect_db()
    cur.execute('''
        SELECT 
            artists.name as artist,
            songs.title as title,
            strftime('%d.%m.%Y',playedSongs.played_at) as date,
            strftime('%H:%M:%S',playedSongs.played_at) as time
        FROM playedSongs
        INNER JOIN songs ON songs.song_id = playedSongs.song
        INNER JOIN artists ON artists.artist_id = songs.artist
    ''')
    result = cur.fetchall()
    cur.close()
    conn.close()
    return json.dumps(result)


@app.route('/deleteAll')
@cross_origin()
def deleteAll():
    conn, cur = db.connect_db()
    cur.execute('DELETE FROM artists WHERE 1')
    cur.execute('DELETE FROM songs WHERE 1')
    cur.execute('DELETE FROM playedSongs WHERE 1')
    conn.commit()
    cur.close()
    conn.close()
    return 'ok'


@app.route('/getPlaylistAtDate', methods=['POST'])
@cross_origin()
def getPlaylistAtDate():
    selectedDate = datetime.strptime(request.get_json()['date'], "%Y-%m-%dT%H:%M:%S.%fZ").date()
    conn, cur = db.connect_db()
    cur.execute('''
        SELECT artists.name, songs.title
        FROM playedSongs
        INNER JOIN songs ON songs.song_id = playedSongs.song
        INNER JOIN artists ON artists.artist_id = songs.artist
        WHERE date(played_at) = ?
        ORDER BY playedSongs.played_at ASC
    ''', (selectedDate,))
    result = cur.fetchall()
    cur.execute('SELECT name FROM djlists LEFT JOIN events ON events.event_id = djlists.event WHERE date = ?',(selectedDate, ))
    res = cur.fetchone()
    event = ""
    if res is not None:
        event = res["name"]
    cur.close()
    conn.close()
    return json.dumps({"result": result, "event": event})


@app.route('/getLastDateWithEntrys')
@cross_origin()
def getLastDateWithEntrys():
    conn, cur = db.connect_db()
    cur.execute('SELECT played_at FROM playedSongs Where played_at = (SELECT max(played_at) FROM playedSongs)')
    res = cur.fetchone()
    cur.close()
    conn.close()
    lastDate = datetime.strptime(res["played_at"], "%Y-%m-%d %H:%M:%S.%f").strftime('%Y-%m-%d')
    return json.dumps({"lastDate": lastDate})


@app.route('/getDjs')
@cross_origin()
def getDjs():
    conn, cur = db.connect_db()
    cur.execute('Select * from diskjockeys')
    res = cur.fetchall()
    cur.close()
    conn.close()
    return json.dumps(res)


@app.route('/makeDj', methods=['POST'])
@cross_origin()
def makeDj():
    name = request.get_json()["name"]
    conn, cur = db.connect_db()
    cur.execute('SELECT * from diskjockeys WHERE name=?', (name,))
    res = cur.fetchone()
    if res is None or len(res) <= 0:
        cur.execute('INSERT INTO diskjockeys(name) VALUES(?)', (name,))
        conn.commit()
    cur.execute('SELECT * from diskjockeys')
    res = cur.fetchall()
    cur.close()
    conn.close()
    return json.dumps(res)


@app.route('/deleteDj', methods=['POST'])
@cross_origin()
def deleteDj():
    name = request.get_json()["name"]
    conn, cur = db.connect_db()
    cur.execute('SELECT * FROM diskjockeys WHERE name = ?', (name,))
    test = cur.fetchall()
    if test is not None or len(test) > 0:
        cur.execute('DELETE FROM diskjockeys WHERE name = ?', (name,))
    cur.execute('SELECT * FROM diskjockeys')
    res = cur.fetchall()
    cur.close()
    conn.close()
    return json.dumps(res)


@app.route('/getEvents')
@cross_origin()
def getEvents():
    conn, cur = db.connect_db()
    cur.execute('SELECT * FROM events')
    res = cur.fetchall()
    cur.close()
    conn.close()
    return json.dumps(res)


@app.route('/makeEvent', methods=['POST'])
@cross_origin()
def makeEvent():
    name = request.get_json()["name"]
    catchphrase = request.get_json()["catchphrase"]
    conn, cur = db.connect_db()
    cur.execute('SELECT * FROM events WHERE name=?', (name,))
    test = cur.fetchall()
    if test is None or len(test) == 0:
        cur.execute('INSERT INTO events(name, catchphrase) VALUES(?, ?)', (name, catchphrase))
        conn.commit()
        print('created')
    else:
        print('exists')
    cur.execute('SELECT * FROM events')
    res = cur.fetchall()
    cur.close()
    conn.close()
    return json.dumps(res)


@app.route('/deleteEvent', methods=['POST'])
@cross_origin()
def deleteEvent():
    name = request.get_json()["name"]
    conn, cur = db.connect_db()
    cur.execute('SELECT * FROM events WHERE name = ?', (name,))
    test = cur.fetchall()
    if test is not None and len(test) > 0:
        cur.execute('DELETE FROM events WHERE name = ?', (name,))
        conn.commit()
    cur.execute('SELECT * FROM events')
    res = cur.fetchall()
    cur.close()
    conn.close()
    return json.dumps(res)


def getMonthDates(m, y):
    m = int(m)
    y = int(y)
    d = date(y,m, 1)
    dates = []
    while d.day < monthrange(y, m)[1]:
        if d.weekday() == 4 or d.weekday() == 5:
            dates.append(d)
        d += timedelta(1)
    if d.weekday() == 4 or d.weekday() == 5:
        dates.append(d)
    return dates

def makeEventList():
    conn, cur = db.connect_db()
    cur.execute('''
               SELECT * FROM djlists_djs
               INNER JOIN diskjockeys ON diskjockeys.dj_id = djlists_djs.dj
               INNER JOIN djlists ON djlists.djlist_id = djlists_djs.djlist_entry
               LEFT JOIN events ON djlists.event = events.event_id
               ''')
    res = cur.fetchall()

    cur.close()
    conn.close()


@app.route('/loadCurrEvents')
@cross_origin()
def loadCurrEvents():
    month, year = request.args.to_dict().values()
    conn, cur = db.connect_db()
    cur.execute('''
        SELECT * FROM djlists
        LEFT JOIN events ON djlists.event = events.event_id
        WHERE djlists.month = ? AND djlists.year = ?
        ''', (month, year))
    res = cur.fetchall()
    if res is None or len(res) == 0:
        dates = getMonthDates(month, year)
        dates = [dat.strftime('%Y-%m-%d') for dat in dates]
        for dat in dates:
            cur.execute('''INSERT INTO djlists(date, month, year) VALUES(?, ?, ?)''', (dat, month, year))
            djlist_id = cur.lastrowid
            cur.execute('''INSERT OR IGNORE INTO djlists_djs (djlist_entry, dj) VALUES (?, ?)''', (djlist_id, 2))
            conn.commit()
    cur.execute('''
            SELECT * FROM djlists
            LEFT JOIN events ON djlists.event = events.event_id
            WHERE djlists.month = ? AND djlists.year = ?
            ''', (month, year))
    resEvents = cur.fetchall()
    dates = list(set([event["date"] for event in res]))
    dates.sort()
    currEvents = []
    for dat in dates:
        cur.execute('SELECT date, dj FROM djlists_djs INNER JOIN djlists ON djlists.djlist_id = djlists_djs.djlist_entry')
        res = cur.fetchall()
        dj_ids = [event["dj"] for event in res if event["date"] == dat]
        names = []
        if len(dj_ids) > 0:
            for dj in dj_ids:
                cur.execute('''SELECT name FROM diskjockeys WHERE dj_id = ?''', (dj,))
                name = cur.fetchone()["name"]
                names.append(None if name == '' else name)
        event = [event["name"] for event in resEvents if event["date"] == dat][0]
        currEvents.append({
            "date": dat,
            "event": event,
            "djs": names
        })
    cur.close()
    conn.close()
    return json.dumps(currEvents)


@app.route('/createEvents', methods=['POST'])
@cross_origin()
def createEvents():
    events, month, year = request.get_json().values()
    for index, event in enumerate(events):
        if event["event"] is not None:
            currEvent = event["event"]
            currDjs = event["djs"]
            currDate = event["date"]
            resultingEvent = createEvent(currEvent, currDate, month, year, currDjs)
            events[index] = resultingEvent
    return json.dumps(events)


def createEvent(event, date, month, year, djs):
    conn, cur = db.connect_db()
    cur.execute('''SELECT * FROM djlists WHERE date = ? AND month = ? AND YEAR = ?''', (date, month, year))
    res = cur.fetchone()
    cur.execute('SELECT event_id FROM events WHERE name = ?', (event,))
    event = cur.fetchone()
    event = event["event_id"] if event is not None else None
    if res is None:
        cur.execute('''INSERT INTO djlists(event, date, month, year) VALUES (?, ?, ?, ?)''', (event, date, month, year))
        conn.commit()
        cur.execute('SELECT djlist_id FROM djlists WHERE date = ? AND month = ? AND year = ?', (date, month, year))
        djlist_entry = cur.fetchone()['djlist_id']
        cur.execute('''INSERT OR IGNORE INTO djlists_djs (djlist_entry, dj) VALUES (?, ?)''', (djlist_entry, 1))
        conn.commit()
    else:
        cur.execute('''UPDATE djlists SET event = ? WHERE date = ? AND month = ? AND year = ?''',
                    (event, date, month, year))
        conn.commit()
    cur.execute('SELECT djlist_id FROM djlists WHERE date = ? AND month = ? AND year = ?', (date, month, year))
    djlist_entry = cur.fetchone()['djlist_id']
    cur.execute('''DELETE FROM djlists_djs WHERE djlist_entry = ?''', (djlist_entry,))
    conn.commit()
    for dj in djs:
        cur.execute('''SELECT dj_id FROM diskjockeys WHERE name = ?''', (dj,))
        dj_id = cur.fetchone()
        dj_id = 2 if dj_id is None else dj_id["dj_id"]
        cur.execute('''INSERT INTO djlists_djs (djlist_entry, dj) VALUES (?, ?)''', (djlist_entry, dj_id))
        conn.commit()
    cur.execute('''
        SELECT * FROM djlists_djs
        INNER JOIN diskjockeys ON diskjockeys.dj_id = djlists_djs.dj
        INNER JOIN djlists ON djlists.djlist_id = djlists_djs.djlist_entry
        LEFT JOIN events ON djlists.event = events.event_id
        ''')
    res = cur.fetchall()
    cur.close()
    conn.close()
    resultingEvent = {"date": date, "event": res[0]["name"] if len(res) >0 and "name" in res[0].keys() else None, "djs": djs}
    return resultingEvent

@app.route('/addDate', methods=['POST'])
@cross_origin()
def addDate():
    currDate, month, year = request.get_json().values()
    conn, cur = db.connect_db()
    cur.execute('SELECT * FROM djlists WHERE date = ? and month = ? and year = ?', (currDate, month, year))
    res = cur.fetchone()
    if res is None:
        cur.execute('INSERT INTO djlists (date,year,month) VALUES (?, ?, ?)', (currDate, year, month))
        djlist_entry = cur.lastrowid
        cur.execute('INSERT INTO djlists_djs (djlist_entry, dj) VALUES (?, ?)', (djlist_entry, 2))
        conn.commit()
    cur.execute('''
            SELECT * FROM djlists_djs
            INNER JOIN diskjockeys ON diskjockeys.dj_id = djlists_djs.dj
            INNER JOIN djlists ON djlists.djlist_id = djlists_djs.djlist_entry
            LEFT JOIN events ON djlists.event = events.event_id
            ''')
    res = cur.fetchall()
    cur.close()
    conn.close()
    return json.dumps(res)



@app.route('/remDate', methods=['POST'])
@cross_origin()
def remDate():
    date, month, year = request.get_json().values()
    conn, cur = db.connect_db()
    cur.execute('SELECT * FROM djlists WHERE date = ? and month = ? and year = ?', (date, month, year))
    res = cur.fetchone()
    if res is not None:
        id = res["djlist_id"]
        cur.execute('DELETE FROM djlists_djs WHERE djlist_entry = ?', (id,))
        cur.execute('DELETE FROM djlists WHERE djlist_id = ?', (id,))
        conn.commit()
    cur.execute('''
                SELECT * FROM djlists_djs
                INNER JOIN diskjockeys ON diskjockeys.dj_id = djlists_djs.dj
                INNER JOIN djlists ON djlists.djlist_id = djlists_djs.djlist_entry
                LEFT JOIN events ON djlists.event = events.event_id
                ''')
    res = cur.fetchall()
    cur.close()
    conn.close()
    return json.dumps(res)

@app.route('/getPreview')
@cross_origin()
def getPreview():
    month, year, y0, fs0, fs1, fs2, deltay0, deltay1 = request.args.to_dict().values()
    months = ['Januar', 'Februar', 'M??rz', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
    monthText = months[int(month)-1]
    conn, cur = db.connect_db()
    cur.execute('''
                SELECT * FROM djlists
                LEFT JOIN events ON djlists.event = events.event_id
                WHERE month = ? AND year = ?
                ORDER BY date ASC
                ''',(month, year))
    res = cur.fetchall()
    djprogramm = [f'{monthText} {str(year)}', '|'.join([y0, fs0, fs1, fs2, deltay0, deltay1])]
    print(djprogramm)
    for event in res:
        cur.execute('SELECT name FROM djlists_djs INNER JOIN diskjockeys ON diskjockeys.dj_id = djlists_djs.dj WHERE djlist_entry = ?', (event["djlist_id"],))
        djs = [dj["name"] for dj in cur.fetchall()]
        oDateTime = datetime.strptime(event["date"],'%Y-%m-%d')
        locale.setlocale(locale.LC_TIME, 'de_DE')
        dateText = oDateTime.strftime('%a.%d.%m.')
        djText = f'mit DJ {djs[0]}' if (len(djs) == 1 and djs[0] != '') else f'mit Djs {" und ".join(djs)}' if len(djs) > 1 else ''
        eventText = f'{dateText}|{event["name"]}|{event["catchphrase"]} {djText}'
        djprogramm.append(eventText)
    enviVar = djprogramm[1].split('|')

    y0 = int(enviVar[0])
    fs0 = int(enviVar[1])
    fs1 = int(enviVar[2])
    fs2 = int(enviVar[3])
    deltay0 = int(enviVar[4])
    deltay1 = int(enviVar[5])

    programm = djprogramm[2:]

    pic = cv2.imread('./djplan.jpg')
    fontpath = "./LongIslandAntiqua.ttf"

    fontUe = ImageFont.truetype(fontpath, fs0)
    fontEv = ImageFont.truetype(fontpath, fs1)
    fontSt = ImageFont.truetype(fontpath, fs2)

    x = [192, 400, 400]
    fonts = [fontEv, fontEv, fontSt]
    for (i, event) in enumerate(programm):
        eventItems = event.split('|')
        y1 = y0 + deltay0 * i
        y2 = y1 + deltay1
        y = [y1, y1, y2]
        for (j, item) in enumerate(eventItems):
            img_pil = Image.fromarray(pic)
            draw = ImageDraw.Draw(img_pil)
            draw.text((x[j], y[j]), item, font=fonts[j], fill=(255, 255, 255, 1))
            pic = np.array(img_pil)

    draw = ImageDraw.Draw(img_pil)
    draw.text((525, 502), (monthText+" "+str(year)).upper(), font=fontUe, fill=(255, 255, 255, 1))
    pic = np.array(img_pil)
    name = "./eisbaer-preview.jpg"
    cv2.imwrite(name, pic)
    with open('eisbaer-preview.jpg', "rb") as file:
        encoded_image = base64.b64encode(file.read())
    cur.close()
    conn.close()
    return encoded_image

@app.route("/getNextEvents")
@cross_origin()
def getNextEvents():
    conn, cur = db.connect_db()
    cur.execute('SELECT diskJockeys.name as DjName, events.name, events.catchphrase, djlists.date FROM djlists_djs INNER JOIN djlists ON djlists.djlist_id = djlists_djs.djlist_entry INNER JOIN diskJockeys ON djlists_djs.dj = diskJockeys.dj_id LEFT JOIN events ON djlists.event = events.event_id where date > DATE() ORDER BY date ASC LIMIT 6')
    result = cur.fetchall()
    return result

