#!/bin/bash

# UMM and Water Values Dashboard Prototype Startup Script

echo "======================================"
echo "Starting Dashboard Prototype"
echo "======================================"
echo ""

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    echo "Error: Please run this script from the main_prototype directory"
    exit 1
fi

# Check if node_modules exist
if [ ! -d "backend/node_modules" ] || [ ! -d "frontend/node_modules" ]; then
    echo "Installing dependencies..."
    npm run install-all
    echo ""
fi

echo "Starting backend server (port 5000)..."
echo "Starting frontend dev server (port 3000)..."
echo ""
echo "The application will open in your browser at http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""
echo "======================================"

# Start both servers
npm start
