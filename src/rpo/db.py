import logging
from datetime import datetime
from multiprocessing import Lock
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Iterator

import duckdb
from polars import DataFrame

from rpo.exceptions import InvalidIdentificationOption
from rpo.models import FileChangeCommitRecord

logger = logging.getLogger(__name__)


global_lock = Lock()
gconnection = duckdb.connect()


class DB:
    def __init__(self, name: str, initialize=False, in_memory=False) -> None:
        self.name = name

        self._in_memory = in_memory
        self._file_path = None

        self._created = False
        if initialize:
            self.create_tables()

    @property
    def file_path(self):
        if not self._file_path:
            if self._in_memory:
                self._file_path = ":memory:"
            else:
                tmp_dir = Path(gettempdir()) / "rpo-data"
                tmp_dir.mkdir(exist_ok=True, parents=True)
                self._file_path = tmp_dir / f"{self.name}.ddb"
        return self._file_path

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        global gconnection
        if not self._in_memory and not self._created:
            gconnection = duckdb.connect(self.file_path).cursor()
            self._created = True
        return gconnection

    def _execute_many(self, query, data):
        return self.conn.executemany(query, data)

    def _execute(
        self,
        query,
        params: list[Any] | dict[str, Any] | None = None,
    ) -> DataFrame:
        return self.conn.execute(query, params).pl()

    def _execute_sql(self, query):
        return self.conn.sql(query)

    def create_tables(self):
        _ = self._execute_sql("""
                CREATE OR REPLACE TABLE file_changes (
                    repository VARCHAR,
                    sha VARCHAR(40),
                    author_name VARCHAR,
                    author_email VARCHAR,
                    committer_name VARCHAR,
                    committer_email VARCHAR,
                    gpgsig VARCHAR,

                    authored_datetime DATETIME,
                    committed_datetime DATETIME,
                    filename VARCHAR,
                    insertions UBIGINT,
                    deletions UBIGINT,
                    lines UBIGINT,
                    change_type VARCHAR(1),
                    is_binary BOOLEAN)
                 """)

        _ = self._execute_sql("""CREATE OR REPLACE TABLE sha_files (
                sha VARCHAR(40),
                filename VARCHAR
                )
                """)

        logger.info("Created tables")

    def _check_group_by(self, group_by: str) -> str:
        default = "author_email"
        if group_by not in {
            "author_email",
            "author_name",
            "commiter_name",
            "committer_email",
        }:
            logger.warning(
                f"Invalid group by key: {group_by}, using '{default}'",
            )
            return default
        return group_by

    def insert_sha_files(self, data: Iterator[tuple[str, str]]):
        return self._execute_many("""INSERT INTO sha_files VALUES ($1, $2)""", data)

    def sha_file_datetime(self):
        """gets filenames and the date of the commit"""
        return self._execute(
            "SELECT committed_datetime, sf.sha, sf.filename FROM file_changes fc JOIN sha_files sf ON fc.sha = sf.sha",
        ).sort(by="filename")

    def author_file_change_report(self, author: str, by: str = "email"):
        if by not in {"email", "name"}:
            raise InvalidIdentificationOption("Must be either 'email' or 'name'")
        query = f"""SELECT author_{by}, filename, sum(lines) FROM file_changes
               WHERE author_{by} = $1
               GROUP BY author_email, filename"""
        return self._execute(
            query,
            [author],
        )

    def insert_file_changes(self, revs: list[FileChangeCommitRecord]):
        to_insert = [
            r.model_dump(
                exclude=set(
                    [
                        "summary",
                    ]
                )
            )
            for r in revs
        ]
        query = """INSERT into file_changes VALUES (
                    $repository,
                    $sha,
                    $author_name,
                    $author_email,
                    $committer_name,
                    $committer_email,
                    $gpgsig,
                    $authored_datetime,
                    $committed_datetime,
                    $filename,
                    $insertions,
                    $deletions,
                    $lines,
                    $change_type,
                    $is_binary
                )"""
        try:
            if to_insert:
                _ = self._execute_many(query, to_insert)
            return self.all_file_changes()
        except (duckdb.InvalidInputException, duckdb.ConversionException) as e:
            logger.error(f"Failure to insert file change records: {e}")
        logger.info(f"Inserted {len(revs)} file change records into {self.file_path}")

    def change_count(self) -> int:
        return self._execute(
            "select count(distinct sha) as commit_count from file_changes",
        )["commit_count"][0]

    def commits_per_file(self) -> DataFrame:
        return self._execute(
            """SELECT filename, count(DISTINCT sha) AS count
              FROM file_changes
              GROUP BY filename
              ORDER BY count DESC""",
        )

    def changes_and_deletions_per_file(self) -> DataFrame:
        return self._execute(
            """SELECT filename, sum(insertions + deletions) AS count
              FROM file_changes
              GROUP BY filename
              ORDER BY count DESC""",
        )

    def all_file_changes(self) -> DataFrame:
        return self._execute(
            "SELECT * from file_changes order by filename",
        )

    def get_latest_change_tuple(self) -> tuple[datetime, str | None]:
        res = self._execute_sql(
            "SELECT authored_datetime, sha FROM file_changes ORDER BY authored_datetime DESC LIMIT 1",
        ).fetchall()
        return tuple(*res) or (datetime.min, None)

    def changes_by_user(self, group_by: str) -> DataFrame:
        group_by = self._check_group_by(group_by)
        # NOTE: you cannot use duckdb parameters to set group by clause, so do this to prevent injection
        query = f"""SELECT {group_by}, count(DISTINCT sha) as count from file_changes GROUP BY {group_by} ORDER BY count"""
        return self._execute(query)
