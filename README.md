# Chatbot UI

A web-based chatbot interface that uses Groq's LLM models to provide intelligent responses with PDF document processing support and multi-language capabilities.

Deployed live on Render: https://ngo-chatbot.onrender.com
(Due to limited Render resources, the website might take some time to run optimally)

## Features

- 🤖 Integrated with multiple LLM models through Groq API
  - LLaMA 3 8B & 70B
  - Mixtral 8x7B
  - Gemma 7B
- 📁 PDF document analysis and context extraction
- 🌐 Automatic language detection and translation
- 💬 Persistent conversation history
- 🎨 Clean, modern dark-themed UI
- 🔄 Model switching without losing context
- To switch languages use terms like {"speak in", "talk in", "reply in", "respond in", 
        "use", "switch to", "change to", "change language to",
        "habla en", "parle en", "sprich in", "parla in"}

## Getting Started

### Prerequisites

- Python 3.8+
- Groq API key - [Get one here](https://console.groq.com)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/SpontaneousSecret/ngo_chatbot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your Groq API key:
   ```
   GROQ_API_KEY="your_groq_api_key_here"
   ```

### Running the Application

Start the FastAPI server:
```bash
uvicorn main:app --reload
```

The application will be available at `http://localhost:8000`.

## Usage

### Web Interface

1. Open your browser and navigate to `http://localhost:8000`
2. Type your message in the input box and press Enter or click the send button
3. Upload PDFs for document analysis by using the attach button
4. Change models via the dropdown in the top right corner

### API Endpoints

- `GET /` - Serves the web interface
- `GET /models` - Lists all available models
- `POST /chat` - Sends a message to the chatbot
- `GET /conversations` - Lists all conversations
- `GET /conversations/{conversation_id}` - Gets a specific conversation
- `DELETE /conversations/{conversation_id}` - Deletes a conversation
- `PUT /conversations/{conversation_id}/model` - Changes the model for a conversation

## API Reference

### Chat Endpoint

```
POST /chat
```

**Parameters:**
- `message` (form) - The user's message
- `pdf` (file, optional) - PDF file to provide context
- `model_id` (form, default: "llama3-8b") - Model ID to use
- `conversation_id` (form, optional) - ID of existing conversation

**Response:**
```json
{
  "response": "The bot's response",
  "conversation_id": "unique-conversation-id",
  "model_id": "llama3-70b"
}
```

## Architecture

- **Frontend**: HTML, CSS, JavaScript
- **Backend**: FastAPI (Python)
- **LLM Provider**: Groq API
- **Document Processing**: PDFPlumber
- **Language Processing**: LangDetect, Deep-Translator

## Project Structure

```
├── main.py                # FastAPI application
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create this)
├── static/                # Static web files
│   ├── index.html         # Web interface
│   ├── style.css          # CSS styles
│   └── script.js          # Frontend JavaScript
└── tools/                 # Utility modules
    ├── pdf_tool.py        # PDF processing utilities
    └── language_tool.py   # Language detection and translation
```

## Development

### Adding New Models

To add a new model, update the `AVAILABLE_MODELS` dictionary in `main.py`:

```python
AVAILABLE_MODELS = {
    "new-model": {
        "id": "model-id-from-groq",
        "provider": "groq",
        "max_tokens": 8192,
        "description": "Description of the model"
    },
    # ... existing models
}
```

### Extending the UI

The frontend UI is built with vanilla JavaScript. To extend it:

1. Modify the HTML structure in `static/index.html`
2. Update the styles in `static/style.css`
3. Add functionality in `static/script.js`

## Future Improvements

- Add authentication for user accounts
- Implement file attachments besides PDF
- Add search functionality for conversation history
- Support for streaming responses
- Database integration for persistent storage

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/)
- [Groq](https://groq.com/)
- [PDFPlumber](https://github.com/jsvine/pdfplumber)
