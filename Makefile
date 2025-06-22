.PHONY: integration test test_cli


all: test test_cli

integration:
	uv run py.test -m integration

test_slow:
	uv run --env-file .env py.test -m 'not integration'

test:
	uv run --env-file .env py.test -m 'not slow and not integration'

test_cli:
	. ./test_cli.sh
