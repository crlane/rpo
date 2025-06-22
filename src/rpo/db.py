import logging
from pathlib import Path
from tempfile import mkdtemp

import duckdb

from rpo.models import FileChangeCommitRecord

logger = logging.getLogger(__name__)


class DB:
    def __init__(self, name: str, in_memory=False) -> None:
        self.name = name
        self._file_path = None
        if not in_memory:
            self._file_path = Path(mkdtemp(prefix="rpo-")) / f"{self.name}.ddb"

        if self._file_path:
            self.con = duckdb.connect(self._file_path)
        else:
            self.con = duckdb.connect()

    def create_tables(self):
        _ = self.con.sql("""
                CREATE OR REPLACE TABLE file_changes (
                    repository VARCHAR,
                    sha VARCHAR,
                    author_name VARCHAR,
                    author_email VARCHAR,
                    committer_name VARCHAR,
                    committer_email VARCHAR,
                    gpgsig VARCHAR,

                    authored_datetime DATETIME,
                    committed_datetime DATETIME,
                    filename VARCHAR,
                    insertions UHUGEINT,
                    deletions UHUGEINT,
                    lines UHUGEINT,
                    change_type VARCHAR(1),
                    is_binary BOOLEAN
                );
            """)
        logger.info("Created tables")

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
            _ = self.con.executemany(query, to_insert)
        except (duckdb.InvalidInputException, duckdb.ConversionException) as e:
            logger.error(f"Failure to insert file change records: {e}")
        logger.info(
            f"Inserted {len(revs)} file change records into {self._file_path if self._file_path else 'memory'}"
        )
