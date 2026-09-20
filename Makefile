up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f app

test:
	pytest -q

health:
	curl -s http://localhost:8000/health | python -m json.tool
