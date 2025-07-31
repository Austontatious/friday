#!/bin/bash

echo "🛠️  Starting FRIDAY VSCode Extension Setup..."

# Check for Node.js
if ! command -v node &> /dev/null
then
    echo "❌ Node.js not found. Please install it from https://nodejs.org/"
    exit 1
fi

# Check for npm
if ! command -v npm &> /dev/null
then
    echo "❌ npm not found. Please install it with Node.js."
    exit 1
fi

# Check for VSCode CLI
if ! command -v code &> /dev/null
then
    echo "❌ VSCode CLI ('code') not found."
    echo "➡️  Open VSCode → Command Palette → 'Shell Command: Install 'code' command in PATH'"
    exit 1
fi

echo "✅ Dependencies check passed."

# Install dependencies
echo "📦 Installing node modules..."
npm install

# Compile the extension
echo "🧱 Compiling TypeScript..."
npm run compile

# Install extension
echo "🚀 Installing extension into VSCode..."
code --install-extension .

echo "🎉 FRIDAY extension installed!"
echo "💡 You can now open VSCode and run 'Ask FRIDAY Anything' from the Command Palette."

# Optional: prompt to launch VSCode in current folder
read -p "👉 Launch VSCode in this folder now? (y/n): " launch
if [[ "$launch" == "y" ]]; then
    code .
fi
