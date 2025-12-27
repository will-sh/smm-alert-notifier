#!/bin/bash
# Multi-platform build script for SMM Alert Receiver Docker image
# Builds for both AMD64 (Intel/AMD) and ARM64 (Apple Silicon, ARM servers)

set -e  # Exit on error

echo "=========================================="
echo "Multi-Platform Docker Build"
echo "=========================================="
echo ""

# Configuration
IMAGE_NAME="smm-alert-receiver"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DOCKER_HUB_USERNAME="${DOCKER_HUB_USERNAME}"

# Check if DOCKER_HUB_USERNAME is set
if [ -z "${DOCKER_HUB_USERNAME}" ]; then
    echo "❌ Error: DOCKER_HUB_USERNAME environment variable is not set!"
    echo ""
    echo "Please set your Docker Hub username:"
    echo "  export DOCKER_HUB_USERNAME=your-username"
    echo "  ./docker-build-multiplatform.sh"
    echo ""
    exit 1
fi

FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
REMOTE_IMAGE="${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${IMAGE_TAG}"

# Platforms to build for
PLATFORMS="linux/amd64,linux/arm64"

echo "Configuration:"
echo "  Image: ${FULL_IMAGE_NAME}"
echo "  Remote: ${REMOTE_IMAGE}"
echo "  Platforms: ${PLATFORMS}"
echo ""

# Check if Docker Buildx is available
if ! docker buildx version &> /dev/null; then
    echo "❌ Error: Docker Buildx is not available!"
    echo ""
    echo "Docker Buildx is required for multi-platform builds."
    echo "Please upgrade Docker to version 19.03 or higher."
    exit 1
fi

echo "✅ Docker Buildx is available"
echo ""

# Create or use existing builder
BUILDER_NAME="multiplatform"
echo "Setting up buildx builder..."

# Check if builder exists
if docker buildx inspect ${BUILDER_NAME} &> /dev/null; then
    echo "Using existing builder: ${BUILDER_NAME}"
    docker buildx use ${BUILDER_NAME}
else
    echo "Creating new builder: ${BUILDER_NAME}"
    docker buildx create --name ${BUILDER_NAME} --use --driver docker-container
fi

echo ""
echo "Building multi-platform image..."
echo "This may take several minutes as it builds for multiple architectures..."
echo ""

# Build and push to Docker Hub (multi-platform requires push, cannot load locally)
if [ -n "${DOCKER_HUB_USERNAME}" ]; then
    echo "Building and pushing to Docker Hub..."
    echo "Note: You must be logged in to Docker Hub (docker login)"
    echo ""
    
    # Check if logged in to Docker Hub
    if ! docker info 2>/dev/null | grep -q "Username"; then
        echo "⚠️  Not logged in to Docker Hub. Attempting login..."
        docker login
        if [ $? -ne 0 ]; then
            echo "❌ Docker Hub login failed!"
            exit 1
        fi
    fi
    
    echo "✅ Authenticated with Docker Hub"
    echo ""
    
    # Build and push (only tag with remote image name)
    docker buildx build \
        --platform ${PLATFORMS} \
        --tag ${REMOTE_IMAGE} \
        --push \
        .
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "=========================================="
        echo "✅ Multi-Platform Build Successful!"
        echo "=========================================="
        echo ""
        echo "Image pushed to: ${REMOTE_IMAGE}"
        echo "Platforms: ${PLATFORMS}"
        echo ""
        echo "Pull on any platform:"
        echo "  docker pull ${REMOTE_IMAGE}"
        echo ""
        echo "Run on AMD64 (Intel/AMD):"
        echo "  docker run -d -p 18123:18123 --name smm-alert-receiver ${REMOTE_IMAGE}"
        echo ""
        echo "Run on ARM64 (Apple Silicon/ARM):"
        echo "  docker run -d -p 18123:18123 --name smm-alert-receiver ${REMOTE_IMAGE}"
        echo ""
    else
        echo ""
        echo "❌ Build failed!"
        exit 1
    fi
else
    echo "Building locally (for inspection only)..."
    echo "Note: Multi-platform images cannot be loaded into local Docker"
    echo ""
    
    # Build without pushing (for inspection)
    docker buildx build \
        --platform ${PLATFORMS} \
        --tag ${FULL_IMAGE_NAME} \
        .
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "=========================================="
        echo "✅ Multi-Platform Build Successful!"
        echo "=========================================="
        echo ""
        echo "Note: Image was built but not loaded locally or pushed."
        echo "To push to Docker Hub, set DOCKER_HUB_USERNAME and run:"
        echo "  export DOCKER_HUB_USERNAME=your-username"
        echo "  ./docker-build-multiplatform.sh"
        echo ""
    else
        echo ""
        echo "❌ Build failed!"
        exit 1
    fi
fi

