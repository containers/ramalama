#!/bin/bash

# Sample shell script for testing file upload functionality

echo "Hello, World! This is a test script."

# Function to demonstrate script functionality
test_function() {
    local message="$1"
    echo "Testing: $message"
    return 0
}

# Variables
NAME="Test Script"
VERSION="1.0.0"

# Main execution
echo "Running $NAME version $VERSION"

# Test the function
test_function "file upload functionality"

# Conditional logic
if [ -f "test_file.txt" ]; then
    echo "Test file exists"
else
    echo "Test file does not exist"
fi

# Loop example
for i in {1..3}; do
    echo "Iteration $i"
done

echo "Script completed successfully!" 