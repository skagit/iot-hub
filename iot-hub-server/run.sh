#!/bin/bash
# filepath: /home/matt/Desktop/iot-hub/iot-hub-server/setup-and-run.sh

NPM_PATH=$(which npm)
NODE_PATH=$(which node)

echo "Using npm at: $NPM_PATH"
echo "Using node at: $NODE_PATH"

echo "Step 1: Building UI project..."
cd ../iot-hub-ui
$NPM_PATH install
$NPM_PATH run build

echo "Step 2: Building server project..."
cd ../iot-hub-server
$NPM_PATH install
cp -r ../iot-hub-ui/dist .

echo "Step 4: Starting server on port 80..."
sudo $NODE_PATH main.js