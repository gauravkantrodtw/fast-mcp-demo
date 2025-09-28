#!/bin/bash

# Script to create a deployment package for AWS Lambda following AWS documentation
set -e

echo "Creating AWS Lambda deployment package following AWS documentation..."

# Create package directory (following AWS docs)
PACKAGE_DIR="package"
rm -rf $PACKAGE_DIR
mkdir -p $PACKAGE_DIR

# Generate requirements.txt from pyproject.toml
echo "Generating requirements.txt from pyproject.toml..."
uv export --format requirements-txt > requirements.txt

# Install dependencies in package directory
echo "Installing dependencies in package directory..."
# For x86_64 Lambda
uv pip install --system --target ./package -r requirements.txt

# Alternative: For ARM64 Lambda (uncomment the line below and comment the line above)
# uv pip install --system --target ./package --python-platform aarch64-unknown-linux-gnu --only-binary=:all: -r requirements.txt

# Create zip file with dependencies at root (following AWS docs)
echo "Creating zip file with dependencies at root..."
cd $PACKAGE_DIR
zip -r ../mcp-server-deployment.zip .
cd ..

# Add source code files to root of zip (following AWS docs)
echo "Adding source code files to root of zip..."
zip mcp-server-deployment.zip lambda_handler.py
zip mcp-server-deployment.zip server.py

# Add directories to root of zip
zip -r mcp-server-deployment.zip tools/
zip -r mcp-server-deployment.zip utils/
zip -r mcp-server-deployment.zip data/

# Ensure new utility files are included
echo "Verifying utility files are included..."
zip -l mcp-server-deployment.zip | grep -E "(logger\.py|error_handler\.py)" || echo "Warning: Utility files not found in package"

echo "Deployment package created: mcp-server-deployment.zip"
echo "Package size: $(du -h mcp-server-deployment.zip | cut -f1)"

# Clean up
rm -rf $PACKAGE_DIR

echo "Done! Following AWS Lambda deployment package structure."
