#!/bin/bash
#
# Generate TypeScript types from FastAPI OpenAPI schema
#
# This script fetches the OpenAPI schema from the running FastAPI server
# and generates TypeScript types using openapi-typescript.
#
# Prerequisites:
#   1. Backend server running: make dev
#   2. npm package installed: npm install -g openapi-typescript
#
# Usage:
#   ./scripts/generate-types.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
OUTPUT_FILE="$FRONTEND_DIR/src/generated-types.ts"

API_URL="${API_URL:-http://localhost:8000}"
OPENAPI_URL="$API_URL/openapi.json"

echo "🔍 Fetching OpenAPI schema from $OPENAPI_URL..."

# Check if server is running
if ! curl -s "$OPENAPI_URL" > /dev/null 2>&1; then
    echo "❌ Error: Cannot reach $OPENAPI_URL"
    echo "   Make sure the backend server is running: make dev"
    exit 1
fi

# Check if openapi-typescript is installed
if ! command -v npx &> /dev/null; then
    echo "❌ Error: npx not found. Please install Node.js."
    exit 1
fi

echo "📝 Generating TypeScript types..."

# Generate types using openapi-typescript
npx openapi-typescript "$OPENAPI_URL" -o "$OUTPUT_FILE"

echo "✅ Types generated: $OUTPUT_FILE"

# Add header comment
TEMP_FILE=$(mktemp)
cat > "$TEMP_FILE" << 'EOF'
/**
 * Auto-generated TypeScript types from FastAPI OpenAPI schema.
 *
 * DO NOT EDIT MANUALLY - This file is auto-generated.
 * Run `./scripts/generate-types.sh` to regenerate.
 *
 * @generated
 */

EOF

cat "$OUTPUT_FILE" >> "$TEMP_FILE"
mv "$TEMP_FILE" "$OUTPUT_FILE"

echo ""
echo "📋 Generated types include:"
grep -E "^export (interface|type)" "$OUTPUT_FILE" | head -20 || true
echo "   ... (and more)"
echo ""
echo "💡 Usage in TypeScript:"
echo "   import type { paths, components } from './generated-types'"
echo "   type BookSummary = components['schemas']['BookSummary']"


