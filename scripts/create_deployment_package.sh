#!/bin/bash

# Script to create a deployment package for AWS Lambda using layers
set -e

echo "Creating AWS Lambda deployment package using layers..."

# First, create the layers and minimal package
echo "Creating Lambda layers and minimal package..."
./scripts/create_lambda_layers.sh

# Use the minimal package created by layers script
if [ -f "lambda-layers/mcp-server-minimal.zip" ]; then
    echo "Using minimal deployment package with layers..."
    cp lambda-layers/mcp-server-minimal.zip mcp-server-deployment.zip
    echo "Deployment package created: mcp-server-deployment.zip"
    echo "Package size: $(du -h mcp-server-deployment.zip | cut -f1)"
    echo "✅ Using minimal package with Lambda layers for dependencies"
else
    echo "❌ Minimal package not found! Run create_lambda_layers.sh first."
    exit 1
fi

echo "Done! Using Lambda layers for dependencies."
