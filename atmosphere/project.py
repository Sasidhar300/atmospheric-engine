"""Persistent asset versions, review decisions and serialized budget reservations."""
import hashlib
import json
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import NamedTemporaryFile
from uuid import uuid4

from .providers import Generated, PROVIDERS


def fingerprint(data):
    if not isinstance(data, bytes):
        data = json.dumps(data, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


class Project:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS asset (
                    id TEXT PRIMARY KEY, provider TEXT, job TEXT, role TEXT, file TEXT,
                    sha256 TEXT, spec TEXT, usage TEXT, verdict TEXT, note TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS ledger (
                    id TEXT PRIMARY KEY, provider TEXT, job TEXT, estimate INTEGER,
                    reserved INTEGER, actual INTEGER, status TEXT, usage TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def connect(self):
        db = sqlite3.connect(self.root/"production.sqlite3", timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def rows(self, table):
        if table not in {"asset","ledger"}:
            raise ValueError("Unknown project table")
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]

    def available(self, role):
        return [row for row in self.rows("asset") if row["role"]==role and row["verdict"]=="approved"]

    def approved(self, asset_id, role):
        for row in self.available(role):
            if row["id"] == asset_id:
                return self.path(row)
        raise ValueError(f"Approved {role} asset required: {asset_id}")

    def path(self, row):
        path = self.root/row["file"]
        if fingerprint(path.read_bytes()) != row["sha256"]:
            raise ValueError(f"Asset was changed: {row['id']}")
        return path

    def review(self, asset_id, verdict, note):
        if verdict not in {"approved","rejected"} or not note.strip():
            raise ValueError("Approval or rejection requires a review note")
        with closing(self.connect()) as db, db:
            cursor = db.execute("UPDATE asset SET verdict=?, note=? WHERE id=? AND verdict!='rejected'",
                                (verdict,note,asset_id))
            if not cursor.rowcount:
                raise ValueError("Unknown or previously rejected asset")

    def register(self, provider, spec, generated, job=None):
        asset_id = uuid4().hex[:16]
        file = asset_id+generated.extension
        with NamedTemporaryFile(dir=self.root, delete=False) as temporary:
            temporary.write(generated.content)
        Path(temporary.name).replace(self.root/file)
        job = job or fingerprint([provider,spec])
        with closing(self.connect()) as db, db:
            db.execute("""INSERT INTO asset(id, provider, job, role, file, sha256, spec, usage, verdict, note)
                          VALUES (?,?,?,?,?,?,?,?,?,?)""",
                       (asset_id,provider,job,spec["role"],file,fingerprint(generated.content),
                        json.dumps(spec),json.dumps(generated.usage),"pending",None))
        return asset_id

    def request(self, name, spec, ceiling, dry_run=False, ticket=None, authorize=None, regenerate=None):
        provider = PROVIDERS[name]
        if name == "local":
            spec = dict(spec, source_sha256=fingerprint(Path(spec["file"]).read_bytes()))
        job = fingerprint([name,spec,regenerate])
        estimate = provider.estimate_cents
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("""SELECT * FROM asset WHERE job=? AND verdict!='rejected'
                                     ORDER BY verdict='approved' DESC, rowid DESC LIMIT 1""",(job,)).fetchone()
            used = db.execute("SELECT COALESCE(SUM(MAX(reserved, COALESCE(actual,0))),0) FROM ledger").fetchone()[0]
            rejected = db.execute("SELECT 1 FROM asset WHERE job=? AND verdict='rejected'",(job,)).fetchone()
            plan = dict(job=job,provider=name,role=spec["role"],request=spec,paid=provider.paid,
                        estimated_cents=estimate,remaining_cents=max(0,ceiling-used),
                        cache_hit=existing["id"] if existing else None, requires_regeneration=bool(rejected and not existing))
            if dry_run:
                return plan
            if existing:
                self.path(existing)
                return existing["id"]
            if rejected:
                raise ValueError("Candidate was rejected. Supply a new --regenerate value.")
            if provider.paid:
                if ticket != job or type(authorize) is not int or authorize <= 0:
                    raise ValueError("Use a dry run, then authorize its exact job and reserve a positive number of cents")
                if authorize < (estimate or 0) or used+authorize > ceiling:
                    raise ValueError("Budget reservation is below the estimate or exceeds the remaining ceiling")
                try:
                    db.execute("""INSERT INTO ledger(id,provider,job,estimate,reserved,status)
                                  VALUES (?,?,?,?,?,?)""",(job,name,job,estimate,authorize,"submitted"))
                except sqlite3.IntegrityError as error:
                    raise ValueError("This paid job was already submitted. A new generation needs a new plan and authorization.") from error
                db.commit()
            else:
                db.commit()
        try:
            generated = provider.generate(spec)
            if name == "local" and fingerprint(generated.content) != spec["source_sha256"]:
                raise ValueError("Imported file changed during generation")
            asset_id = self.register(name,spec,generated,job)
        except BaseException:
            if provider.paid:
                self.record(job,"unconfirmed",{})
            raise
        if provider.paid:
            self.record(job,"delivered",generated.usage)
        return asset_id

    def record(self, job, status, usage):
        with closing(self.connect()) as db, db:
            db.execute("UPDATE ledger SET status=?, usage=? WHERE id=?", (status,json.dumps(usage),job))

    def reconcile(self, job, actual):
        if type(actual) is not int or actual < 0:
            raise ValueError("Actual charge must be nonnegative integer cents")
        with closing(self.connect()) as db, db:
            row = db.execute("UPDATE ledger SET actual=?, reserved=0 WHERE id=? AND status!='submitted'",(actual,job))
            if not row.rowcount:
                raise ValueError("Unknown ledger item or request still in progress")
