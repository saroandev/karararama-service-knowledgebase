# Streamlit Frontend Module

Modular Streamlit application for the RAG Chat Assistant.

## Project Structure

```
streamlit-frontend/
├── app.py              # Main application entry point
├── config/            # Configuration and settings
│   └── settings.py    # Application settings
├── components/        # UI Components
│   ├── sidebar.py     # Sidebar component
│   ├── chat.py        # Chat interface
│   ├── documents.py   # Document management
│   ├── settings.py    # Settings modal
│   ├── file_upload.py # File upload handler
│   └── system_status.py # System status indicator
├── utils/            # Utilities
│   ├── api_client.py  # API communication
│   └── state_manager.py # Session state management
├── styles/           # Styling
│   └── custom_css.py  # Custom CSS styles
└── run.sh            # Launch script
```

## Features

- **Modular Architecture**: Clean separation of concerns
- **Reusable Components**: Each UI element is a separate component
- **Centralized State Management**: StateManager handles all session state
- **API Client**: Centralized backend communication
- **Custom Styling**: Separated CSS for easy customization

## Running the Application

### Method 1: Using the shell script
```bash
cd streamlit-frontend
./run.sh
```

### Method 2: Direct command
```bash
cd streamlit-frontend
streamlit run app.py --server.port 8501
```

### Method 3: From project root
```bash
streamlit run streamlit-frontend/app.py
```

## Components

### Sidebar (`components/sidebar.py`)
- Conversation management
- Document listing button
- Settings and user buttons
- Uploaded documents display

### Chat (`components/chat.py`)
- Message display
- Source rendering
- Chat input handling
- API query processing

### Documents (`components/documents.py`)
- Knowledge base document listing
- Search functionality
- Document deletion
- MinIO URL display

### Settings (`components/settings.py`)
- API configuration
- Query settings
- UI preferences

### File Upload (`components/file_upload.py`)
- PDF/document upload
- Progress indication
- Duplicate detection

### System Status (`components/system_status.py`)
- API health check
- Visual status indicator

## Configuration

Edit `config/settings.py` to modify:
- API endpoint URL
- File upload limits
- UI configuration
- Query defaults

## State Management

The `StateManager` class in `utils/state_manager.py` handles:
- Session initialization
- Conversation management
- Message history
- Document tracking

## API Integration

The `APIClient` in `utils/api_client.py` provides:
- Query endpoint
- Document upload
- Document listing
- Document deletion
- Health checks

## Development

To add new features:

1. Create new component in `components/`
2. Import in `app.py`
3. Add to appropriate render location
4. Update state management if needed

## Environment Variables

Required `.env` file in project root:
```env
API_BASE_URL=http://localhost:8080
```

## Dependencies

- streamlit
- requests
- python-dotenv
- uuid
- datetime