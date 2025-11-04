#!/bin/bash
set -e

echo "=============================================="
echo "SwipePads News Scraper - Docker Container"
echo "=============================================="
echo ""

# Initialize database if it doesn't exist
if [ ! -f "/app/data/articles.db" ]; then
    echo "📦 Initializing database..."
    python -c "from src.database import init_db; init_db()"
    echo "✅ Database initialized"
    echo ""
fi

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "your_anthropic_key_here" ]; then
    echo "⚠️  WARNING: ANTHROPIC_API_KEY not configured"
    echo "   AI summarization will not work"
    echo "   Set ANTHROPIC_API_KEY environment variable"
    echo ""
fi

# Show configuration
echo "Configuration:"
echo "  Rate Limit: ${SCRAPER_RATE_LIMIT_SECONDS:-2} seconds"
echo "  Log Level: ${LOG_LEVEL:-INFO}"
echo "  Retention: ${ARTICLE_RETENTION_DAYS:-30} days"
echo ""

# Check database status
ARTICLE_COUNT=$(python -c "from src.database import get_article_count; print(get_article_count())" 2>/dev/null || echo "0")
echo "Current Status:"
echo "  Articles in DB: $ARTICLE_COUNT"
echo ""

echo "=============================================="
echo "Starting: $@"
echo "=============================================="
echo ""

# Execute the main command
exec "$@"
