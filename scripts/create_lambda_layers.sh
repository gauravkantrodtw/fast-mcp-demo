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
    
    # Check if requirements file has actual dependencies (not just comments)
    if ! grep -q "^[^#]" "$requirements_file"; then
        echo "⚠️  No dependencies found for $layer_name, skipping..."
        return 0
    fi
    
    # Create layer directory structure
    mkdir -p $layer_dir/python
    
    # Install dependencies using uv for Lambda layer compatibility
    echo "Installing dependencies for $layer_name..."
    uv pip install -r $requirements_file --target $layer_dir/python --no-deps --upgrade
    
    # Create layer zip
    cd $layer_dir
    zip -r "../${layer_name}.zip" python/
    cd ..
    
    # Get layer size
    layer_size=$(du -h "${layer_name}.zip" | cut -f1)
    echo "✅ Created $layer_name.zip (Size: $layer_size)"
}

# Create multiple layers to stay under 50MB limit
echo "📦 Creating multiple layers..."

# Layer 1: Core MCP dependencies
echo "📦 Creating Layer 1: Core MCP dependencies..."
create_layer "${LAYER_NAME_PREFIX}-core" "$REQUIREMENTS_DIR/layer1-core.txt" "$LAYER_DIR/core"

# Layer 2: Data processing dependencies
echo "📦 Creating Layer 2: Data processing dependencies..."
create_layer "${LAYER_NAME_PREFIX}-data" "$REQUIREMENTS_DIR/layer2-data.txt" "$LAYER_DIR/data"

# Create minimal deployment package (only application code)
echo "📦 Creating minimal deployment package..."
mkdir -p minimal-package

# Copy application files if they exist
[ -f "lambda_handler.py" ] && cp lambda_handler.py minimal-package/
[ -d "tools" ] && cp -r tools/ minimal-package/
[ -d "utils" ] && cp -r utils/ minimal-package/

# Create a simple requirements.txt for the minimal package
cat > minimal-package/requirements.txt << 'EOF'
# Dependencies are provided by Lambda layers
# Only include packages not in layers if any
EOF

cd minimal-package
zip -r "../mcp-server-minimal.zip" .
cd ..

# Get final sizes
echo "📊 Package sizes:"
for layer_zip in *.zip; do
    size=$(du -h "$layer_zip" | cut -f1)
    echo "  $layer_zip: $size"
done

echo "✅ Lambda layers created successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Upload all layers to AWS Lambda"
echo "2. Update Lambda function to use all layers"
echo "3. Deploy minimal package as function code"
echo ""
echo "🔧 Layer ARNs will be needed for Lambda function configuration:"
echo "   - Core Layer: arn:aws:lambda:REGION:ACCOUNT:layer:${LAYER_NAME_PREFIX}-core:1"
echo "   - Data Layer: arn:aws:lambda:REGION:ACCOUNT:layer:${LAYER_NAME_PREFIX}-data:1"
echo "   - Note: boto3 is pre-installed in AWS Lambda, so no layer needed"
