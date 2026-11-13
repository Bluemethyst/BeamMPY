from contextlib import contextmanager
from pathlib import Path
import sqlite3
import uuid


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 5:
                raise RuntimeError("Database is newer than this panel; upgrade BeamMPY.")
            if version < 1:
                db.executescript("""
                    BEGIN IMMEDIATE;
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS servers (
                        id TEXT PRIMARY KEY, name TEXT NOT NULL,
                        directory TEXT NOT NULL UNIQUE, version TEXT,
                        last_error TEXT, process_pid INTEGER,
                        process_created REAL, process_executable TEXT
                    );
                    CREATE TABLE IF NOT EXISTS auth_sessions (
                        token TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    );
                    PRAGMA user_version = 1;
                    COMMIT;
                """)
            if version < 2:
                db.executescript("""
                    BEGIN IMMEDIATE;
                    CREATE TABLE IF NOT EXISTS ignored_imports (directory TEXT PRIMARY KEY);
                    PRAGMA user_version = 2;
                    COMMIT;
                """)
            if version < 3:
                db.execute("BEGIN IMMEDIATE")
                columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
                for name, default in (("is_admin", 0), ("enabled", 1),
                                      ("can_create_servers", 0), ("must_change_password", 0)):
                    if name not in columns:
                        db.execute(f"ALTER TABLE users ADD COLUMN {name} INTEGER NOT NULL DEFAULT {default}")
                db.execute("UPDATE users SET is_admin=1 WHERE id=(SELECT min(id) FROM users) "
                           "AND NOT EXISTS (SELECT 1 FROM users WHERE is_admin=1)")
                db.execute("CREATE TABLE IF NOT EXISTS server_grants ("
                           "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
                           "server_id TEXT NOT NULL REFERENCES servers(id) ON DELETE CASCADE, "
                           "permissions TEXT NOT NULL, PRIMARY KEY(user_id,server_id))")
                db.execute("PRAGMA user_version=3")
            if version < 4:
                db.execute("""CREATE TABLE IF NOT EXISTS statistics_minutes (
                    server_id TEXT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                    minute INTEGER NOT NULL, cpu_sum REAL NOT NULL DEFAULT 0,
                    cpu_n INTEGER NOT NULL DEFAULT 0, cpu_peak REAL,
                    memory_sum REAL NOT NULL DEFAULT 0, memory_n INTEGER NOT NULL DEFAULT 0,
                    memory_peak REAL, players_peak INTEGER, player_n INTEGER NOT NULL DEFAULT 0,
                    joins INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(server_id,minute))""")
                db.execute("CREATE INDEX IF NOT EXISTS statistics_retention ON statistics_minutes(minute)")
                db.execute("""CREATE TABLE IF NOT EXISTS statistics_plugins (
                    server_id TEXT PRIMARY KEY REFERENCES servers(id) ON DELETE CASCADE,
                    path TEXT NOT NULL, token TEXT NOT NULL)""")
                db.execute("PRAGMA user_version=4")
            if version < 5:
                db.execute("""CREATE TABLE IF NOT EXISTS statistics_recent (
                    server_id TEXT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                    time INTEGER NOT NULL, cpu_sum REAL NOT NULL DEFAULT 0,
                    cpu_n INTEGER NOT NULL DEFAULT 0, cpu_peak REAL,
                    memory_sum REAL NOT NULL DEFAULT 0, memory_n INTEGER NOT NULL DEFAULT 0,
                    memory_peak REAL, players_peak INTEGER, player_n INTEGER NOT NULL DEFAULT 0,
                    joins INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(server_id,time))""")
                db.execute("CREATE INDEX IF NOT EXISTS statistics_recent_retention ON statistics_recent(time)")
                db.execute("PRAGMA user_version=5")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def all_servers(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM servers ORDER BY rowid")]

    def server(self, server_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
            return dict(row) if row else None

    def add_server(self, name, directory, version=None):
        server_id = str(uuid.uuid4())
        directory = str(Path(directory).resolve())
        with self.connection() as db:
            db.execute("INSERT INTO servers(id,name,directory,version) VALUES(?,?,?,?)",
                       (server_id, name, directory, version))
            db.execute("DELETE FROM ignored_imports WHERE directory=?", (directory,))
        return self.server(server_id)

    def delete_server(self, server_id):
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO ignored_imports(directory) SELECT directory FROM servers WHERE id=?", (server_id,))
            db.execute("DELETE FROM servers WHERE id=?", (server_id,))

    def update(self, server_id, **fields):
        allowed = {"name", "version", "last_error", "process_pid", "process_created", "process_executable"}
        if not fields or not fields.keys() <= allowed:
            raise ValueError("Invalid server fields")
        with self.connection() as db:
            db.execute("UPDATE servers SET " + ",".join(f"{key}=?" for key in fields) + " WHERE id=?",
                       (*fields.values(), server_id))

    def import_legacy(self, directory):
        directory = Path(directory).resolve()
        if not directory.is_dir():
            return
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO servers(id,name,directory) SELECT ?,?,? WHERE NOT EXISTS (SELECT 1 FROM ignored_imports WHERE directory=?)",
                       (str(uuid.uuid4()), "Existing BeamMP server", str(directory), str(directory)))
