import sqlite3


def connect_db():
    conn = sqlite3.connect('songDB.db')
    conn.row_factory = dict_factory
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS artists(
               artist_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
               name TEXT);
           ''')
    cur.execute('''CREATE TABLE IF NOT EXISTS songs(
               song_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
               title TEXT NOT NULL,
               artist INTEGER NOT NULL,
               FOREIGN KEY(artist) REFERENCES artists(artist_id));
           ''')
    cur.execute('''CREATE TABLE IF NOT EXISTS playedSongs(
               id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
               played_at DATE,
               song NOT NULL,
               FOREIGN KEY(song) REFERENCES song(song_id));
           ''')
    cur.execute('''CREATE TABLE IF NOT EXISTS diskJockeys(
               dj_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
               name TEXT NOT NULL)
       ''')
    cur.execute('''CREATE TABLE IF NOT EXISTS events(
               event_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
               name TEXT NOT NULL,
               catchphrase TEXT)
       ''')
    cur.execute('''CREATE TABLE IF NOT EXISTS djlists(
               djlist_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
               date DATE NOT NULL,
               event INTEGER,
               month INTEGER NOT NULL,
               year INTEGER NOT NULL,
               FOREIGN KEY(event) REFERENCES events(event_id));    
       ''')
    cur.execute('''CREATE TABLE IF NOT EXISTS djlists_djs(
               djlist_entry INTEGER NOT NULL,
               dj INTEGER NOT NULL,
               PRIMARY KEY(djlist_entry, dj)
               FOREIGN KEY(djlist_entry) REFERENCES djlists(djlist_id),
               FOREIGN KEY(dj) REFERENCES diskJockeys(dj_id));
       ''')
    return conn, cur


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

