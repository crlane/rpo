.PHONY: integration test quick_test


integration:
	uv run --env-file .env py.test -m integration

test:
	uv run py.test -m 'not integration'

quick_test:
	uv run py.test -m 'not slow'
