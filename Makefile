.PHONY: up scenario verify replay api down test lint

up:        ## start Kafka, the raw processor and the materializer
	docker compose up -d --build

scenario:  ## run the stop/restart recovery demonstration
	./scripts/scenario.sh

verify:    ## check the active snapshot against the expected results
	docker compose run --rm -T cli verify --stage final

replay:    ## rebuild the marts from Bronze
	docker compose run --rm -T cli replay

api:       ## serve the read API on http://localhost:$${API_PORT:-8000}
	docker compose up -d --no-deps api

down:      ## stop everything but keep Kafka, Parquet and checkpoint volumes
	docker compose down

test:
	pytest -q

lint:
	ruff check .
