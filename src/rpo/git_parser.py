import re

# incremental blame produces an OID as the first line
INC_BLAME_RE = re.compile(
    r"(?P<oid>[a-f0-9]{40})(?P<counts>(\s(\d+)){3}$)", re.MULTILINE
)


class GitParser:
    def __init__(self):
        pass

    def parse_blame_result(self, result: str, blob_id: str, for_path: str, *args):
        keys = (
            "blob_id",
            "path",
            "commit_sha",
            "old_line_loc",
            "new_line_loc",
            "num_lines",
        )
        for match in INC_BLAME_RE.finditer(result):
            oid = match.group("oid")
            old_line_loc, new_line_loc, num_lines = [
                int(a) for a in match.group("counts").strip().split()
            ]
            yield dict(
                zip(
                    keys,
                    (blob_id, for_path, oid, old_line_loc, new_line_loc, num_lines),
                )
            )

    def parse_log_output(self):
        # for line in result:
        #     if not line:
        #         continue
        #     vals = []
        #     vals = [w.strip("'") for w in line.split("|")]
        #     if len(keys) == len(vals):  # file list
        #         prev = base
        #         base = {}
        #         for i, k in enumerate(keys):
        #             if k.endswith("datetime"):
        #                 base[k] = dateparse(vals[i])
        #             else:
        #                 base[k] = vals[i]
        #
        #         if prev:
        #             try:
        #                 _ = self._revs.vstack(DataFrame(prev), in_place=True)
        #             except pl.ShapeError:
        #                 logger.warning(
        #                     f"Found two commit header lines in a row, likely a merge commit: {prev['sha']}"
        #                 )
        #     else:
        #         insertions, deletions, path = line.split("\t")
        #         base["path"] = path
        #         base["insertions"] = int(insertions) if insertions.isdigit() else 0
        #         base["deletions"] = int(deletions) if deletions.isdigit() else 0
        #         base["lines"] = base["insertions"] + base["deletions"]
        #         base["is_binary"] = base["lines"] == 0
        pass
        pass
