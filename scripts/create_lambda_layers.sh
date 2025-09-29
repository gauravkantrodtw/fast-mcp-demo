#!/bin/bash

# Create AWS Lambda Layers for MCP Server Dependencies
# This script creates separate layers for different dependency groups to optimize deployment

set -e

# Configuration
LAYER_NAME_PREFIX="daap-mcp-server"
PYTHON_VERSION="3.12"
ARCHITECTURE="x86_64"  # Change to arm64 if using ARM64 Lambda
LAYER_DIR="lambda-layers"
REQUIREMENTS_DIR="layer-requirements"

echo "🚀 Creating AWS Lambda Layers for MCP Server Dependencies..."

# Clean up previous builds
rm -rf $LAYER_DIR
rm -rf $REQUIREMENTS_DIR
mkdir -p $LAYER_DIR
mkdir -p $REQUIREMENTS_DIR

# Extract dependencies from pyproject.toml and create layer-specific requirements
echo "📦 Extracting dependencies from pyproject.toml..."

# Generate single requirements.txt from pyproject.toml
echo "📦 Generating requirements.txt from pyproject.toml..."
uv export --format requirements-txt > $REQUIREMENTS_DIR/requirements.txt

# Split dependencies into multiple layers to stay under 50MB limit
echo "📦 Splitting dependencies into multiple layers..."

# Layer 1: Core MCP dependencies (fastmcp, urllib3)
echo "fastmcp==2.12.4" > $REQUIREMENTS_DIR/layer1-core.txt
echo "urllib3==2.5.0" >> $REQUIREMENTS_DIR/layer1-core.txt

# Layer 2: Data processing dependencies (pandas)
echo "pandas==2.3.2" > $REQUIREMENTS_DIR/layer2-data.txt

# Note: boto3 is pre-installed in AWS Lambda, so we don't need to include it

echo "✅ Requirements split into multiple layers"

# Function to create a layer
create_layer() {
    local layer_name=$1
    local requirements_file=$2
    local layer_dir=$3
    
    echo "🔨 Creating layer: $layer_name"
    
    # Check if requirements file has actual dependencies (not just comments or empty lines)
    if [ ! -s "$requirements_file" ] || ! grep -q "^[^#]" "$requirements_file"; then
        echo "⚠️  No dependencies found for $layer_name, skipping..."
        return 0
    fi
    
    # Create layer directory structure
    mkdir -p $layer_dir/python
    
    # Install dependencies using uv for Lambda layer compatibility
    echo "Installing dependencies for $layer_name..."
    uv pip install -r $requirements_file --target $layer_dir/python --upgrade
    
    # Create layer zip
    cd $layer_dir
    zip -r "../${layer_name}.zip" python/
    cd - > /dev/null
    
    # Get layer size
    if [ -f "lambda-layers/${layer_name}.zip" ]; then
        layer_size=$(du -h "lambda-layers/${layer_name}.zip" | cut -f1)
        echo "✅ Created $layer_name.zip (Size: $layer_size)"
    else
        echo "❌ Failed to create $layer_name.zip"
        return 1
    fi
}

# Create multiple layers to stay under 50MB limit
echo "📦 Creating multiple layers..."

# Get the absolute path to the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root to ensure relative paths work
cd "$PROJECT_ROOT"

# Layer 1: Core MCP dependencies
echo "📦 Creating Layer 1: Core MCP dependencies..."
create_layer "${LAYER_NAME_PREFIX}-fastmcp-urllib3" "$REQUIREMENTS_DIR/layer1-core.txt" "$LAYER_DIR/core"

# Layer 2: Data processing dependencies
echo "📦 Creating Layer 2: Data processing dependencies..."
create_layer "${LAYER_NAME_PREFIX}-pandas" "$REQUIREMENTS_DIR/layer2-data.txt" "$LAYER_DIR/data"

# Create minimal deployment package (only application code)
echo "📦 Creating minimal deployment package..."
mkdir -p lambda-function-code

# Copy application files if they exist
[ -f "lambda_handler.py" ] && cp lambda_handler.py lambda-function-code/
[ -f "server.py" ] && cp server.py lambda-function-code/
[ -d "tools" ] && cp -r tools lambda-function-code/
[ -d "utils" ] && cp -r utils lambda-function-code/
[ -d "data" ] && cp -r data lambda-function-code/

# Create a simple requirements.txt for the function code
cat > lambda-function-code/requirements.txt << 'EOF'
# Dependencies are provided by Lambda layers
# Only include packages not in layers if any
EOF

cd lambda-function-code
zip -r "../mcp-lambda-function.zip" .
cd ..

# Validate that all expected layers were created
echo "🔍 Validating layer creation..."

# Check for core layer
if [ ! -f "lambda-layers/daap-mcp-server-fastmcp-urllib3.zip" ]; then
    echo "❌ Core layer not created!"
    exit 1
fi

# Check for data layer
if [ ! -f "lambda-layers/daap-mcp-server-pandas.zip" ]; then
    echo "❌ Data layer not created!"
    exit 1
fi

# Check for Lambda function code package
if [ ! -f "mcp-lambda-function.zip" ]; then
    echo "❌ Lambda function code package not created!"
    exit 1
fi

echo "✅ All expected layers created successfully!"

# Get final sizes
echo "📊 Package sizes:"
for layer_zip in lambda-layers/*.zip; do
    if [ -f "$layer_zip" ]; then
        size=$(du -h "$layer_zip" | cut -f1)
        echo "  $(basename "$layer_zip"): $size"
    fi
done
for layer_zip in mcp-lambda-function.zip; do
    if [ -f "$layer_zip" ]; then
        size=$(du -h "$layer_zip" | cut -f1)
        echo "  $layer_zip: $size"
    fi
done

echo "✅ Lambda layers created successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Upload all layers to AWS Lambda"
echo "2. Update Lambda function to use all layers"
echo "3. Deploy Lambda function code package as function code"
echo ""
echo "🔧 Layer ARNs will be needed for Lambda function configuration:"
echo "   - Core Layer: arn:aws:lambda:REGION:ACCOUNT:layer:${LAYER_NAME_PREFIX}-fastmcp-urllib3:1"
echo "   - Data Layer: arn:aws:lambda:REGION:ACCOUNT:layer:${LAYER_NAME_PREFIX}-pandas:1"
echo "   - Note: boto3 is pre-installed in AWS Lambda, so no layer needed"
