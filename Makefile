# SwipePads News Scraper - Makefile
# Convenient commands for Docker deployment

.PHONY: help build up down logs shell test verify clean backup

help: ## Show this help
	@echo "SwipePads News Scraper - Docker Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build Docker image
	docker-compose build

up: ## Start services in daemon mode
	docker-compose up -d
	@echo ""
	@echo "✅ Scraper started! View logs with: make logs"

down: ## Stop all services
	docker-compose down

restart: ## Restart services
	docker-compose restart

logs: ## View logs (follow mode)
	docker-compose logs -f scraper

status: ## Show container status
	docker-compose ps

shell: ## Open shell in container
	docker-compose exec scraper bash

verify: ## Run system verification
	docker-compose run --rm scraper python src/verify_system.py

test: ## Run tests
	docker-compose run --rm scraper python -m pytest tests/ -v

scrape: ## Run manual scrape (10 articles)
	docker-compose run --rm scraper python src/pipeline.py --batch --limit 10 --summarize

export: ## Generate JSON export
	docker-compose run --rm scraper python src/export_cli.py --format json --validate

costs: ## View API costs
	docker-compose run --rm scraper python src/cost_stats.py

stats: ## Show database statistics
	docker-compose exec scraper python -c "from src.database import get_article_count, get_recent_articles; print(f'Total: {get_article_count()}'); print(f'Last 7 days: {len(get_recent_articles(7))}')"

backup: ## Backup database
	mkdir -p backups
	cp data/articles.db backups/articles_$$(date +%Y%m%d_%H%M%S).db
	@echo "✅ Backup created in backups/"

clean: ## Remove containers and volumes (WARNING: deletes data)
	@echo "⚠️  This will delete all data! Press Ctrl+C to cancel..."
	@sleep 5
	docker-compose down -v
	rm -rf data/ images/ logs/ exports/

rebuild: ## Rebuild and restart
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

prod-up: ## Start in production mode
	docker-compose -f docker-compose.prod.yml up -d

prod-down: ## Stop production mode
	docker-compose -f docker-compose.prod.yml down

prod-logs: ## View production logs
	docker-compose -f docker-compose.prod.yml logs -f

# Development commands
dev: ## Start in development mode with verbose logging
	docker-compose run --rm -e LOG_LEVEL=DEBUG scraper python src/scheduler.py

test-scrape: ## Test scraping with fallback files
	docker-compose run --rm scraper python -c "from src.scraper import fetch_page; from src.parser import extract_full_article; html = fetch_page('https://pocketgamer.com', fallback_file='test_data/article1.html'); article = extract_full_article(html, 'https://test'); print(f'✅ Title: {article[\"title\"]}')"
