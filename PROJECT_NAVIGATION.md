# AIhub Project Navigation Guide

Welcome to the AIhub project! This guide will help you navigate the project structure.

## Directory Structure

```
AIhub1.3.1/
├── bin/                   # Binary files and executables
├── config/                # Configuration files
├── db/                    # Database files
├── docs/                  # Documentation
│   └── resources/         # Resource files (text, diagrams, etc.)
├── models/                # AI models
│   ├── downloads/         # Downloaded models ready for use
│   └── backups/           # Backup copies of models
├── python_ai/             # Python ONNX AI server
│   ├── scripts/           # Server management scripts
│   └── docs/              # Server documentation
├── scripts/               # Utility scripts
├── src/                   # Source code
│   ├── api/               # API endpoints
│   ├── cli/               # Command-line interface
│   ├── config/            # Configuration code
│   ├── db/                # Database code
│   ├── harvest/           # Data harvesting
│   ├── ingest/            # Data ingestion
│   ├── middleware/        # Middleware components
│   ├── proxy/             # Proxy functionality
│   ├── routes/            # Route handlers
│   ├── search/            # Search functionality
│   ├── services/          # Service components
│   └── utils/             # Utility functions
├── tests/                 # Test files
├── config.env             # Environment configuration
├── package.json           # Node.js package file
└── README.md              # Project README
```

## Key Components

### AIhub Main Application

The main AIhub application is a Node.js application found in the `src/` directory.

Start the application using the script in the root directory:
```
./scripts/start.ps1
```

### Python ONNX AI Server

The ONNX AI server is a Python application found in the `python_ai/` directory.

Start the server using the AIhub console command:
```
/py
```

Or directly using:
```
./python_ai/start-python-server.ps1
```

### AI Models

AI models are stored in the `models/downloads/` directory. The main model used is `phi-3-mini-onnx-cuda`.

### Documentation

Documentation is stored in the `docs/` directory, with the main README in the root directory.

## Common Tasks

### Starting AIhub

1. Open PowerShell
2. Navigate to the AIhub directory
3. Run `./scripts/start.ps1`

### Downloading a New Model

1. Open PowerShell
2. Navigate to the AIhub directory
3. Run `./scripts/download-onnx-model.ps1`

### Testing the API

1. Start AIhub
2. Use the test files in the `tests/` directory

## Configuration

Edit `config.env` to configure the application. See documentation in `docs/` for more details.