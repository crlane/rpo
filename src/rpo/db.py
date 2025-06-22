import logging
from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from typing import Any

import duckdb
from polars import DataFrame

from rpo.models import FileChangeCommitRecord

logger = logging.getLogger(__name__)


class DB:
    def __init__(self, name: str, in_memory=False) -> None:
        self.name = name
        self._file_path = ":memory:"
        if not in_memory:
            tmp_dir = Path(gettempdir()) / "rpo-data"
            tmp_dir.mkdir(exist_ok=True, parents=True)
            self._file_path = tmp_dir / f"{self.name}.ddb"

        self.con = duckdb.connect(self._file_path)

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
                    insertions UBIGINT,
                    deletions UBIGINT,
                    lines UBIGINT,
                    change_type VARCHAR(1),
                    is_binary BOOLEAN
                );
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
            return self.all_file_changes()
        except (duckdb.InvalidInputException, duckdb.ConversionException) as e:
            logger.error(f"Failure to insert file change records: {e}")
        logger.info(
            f"Inserted {len(revs)} file change records into {self._file_path if self._file_path else 'memory'}"
        )

    def _execute_to_pl_df(
        self, query, params: list[Any] | dict[str, Any] | None = None
    ) -> DataFrame:
        if params:
            return self.con.execute(query, params).pl()
        return self.con.execute(query).pl()

    def change_count(self) -> int:
        return self.con.execute(
            "select count(distinct sha) as commit_count from file_changes"
        ).pl()["commit_count"][0]

    def commits_per_file(self) -> DataFrame:
        return self._execute_to_pl_df("""SELECT filename, count(DISTINCT sha) AS count
              FROM file_changes
              GROUP BY filename
              ORDER BY count DESC""")

    def changes_and_deletions_per_file(self) -> DataFrame:
        return self._execute_to_pl_df("""SELECT filename, sum(insertions + deletions) AS count
              FROM file_changes
              GROUP BY filename
              ORDER BY count DESC""")

    def all_file_changes(self) -> DataFrame:
        return self._execute_to_pl_df("SELECT * from file_changes order by filename")

    def get_latest_change_tuple(self) -> tuple[datetime, str]:
        return tuple(
            *self.con.sql(
                "select authored_datetime, sha from file_changes order by authored_datetime desc limit 1"
            ).fetchall()
        )

    def changes_by_user(self, group_by: str) -> DataFrame:
        group_by = self._check_group_by(group_by)
        # NOTE: you cannot use duckdb parameters to set group by clause, so do this to prevent injection
        query = f"""SELECT {group_by}, count(DISTINCT sha) as count from file_changes GROUP BY {group_by} ORDER BY count"""
        return self._execute_to_pl_df(query)
