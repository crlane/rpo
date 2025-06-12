from typing import Literal

type AggregateBy = Literal["author", "committer"]
type IdentifyBy = Literal["name", "email"]
type SortBy = Literal["user", "numeric", "temporal", "first", "last"] | str
