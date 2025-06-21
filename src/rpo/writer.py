from os import PathLike
from pathlib import Path

from polars import DataFrame


class Writer:
    def __init__(self, locations: list[PathLike[str]]):
        self.output_file_paths = locations

    def write(self, df: DataFrame):
        while self.output_file_paths:
            fp = self.output_file_paths.pop()
            if not isinstance(fp, Path):
                fp = Path(fp)
            if fp.name != "-":
                _ = fp.parent.mkdir(exist_ok=True, parents=True)
                if fp.suffix == ".csv":
                    df.write_csv(fp)
                elif fp.suffix == ".json":
                    df.write_json(fp)
                else:
                    raise ValueError(f"Unsupported filetype: {fp}")
            else:
                print(df)
