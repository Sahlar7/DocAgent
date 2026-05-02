# DocAgent Chrome Extension

A modular Chrome extension that integrates AI research capabilities directly into Google Docs.

## Project Structure

```
docagent_extension/
├── manifest.json                 # Extension configuration
├── background.js                 # Main background service worker
├── content.js                    # Google Docs integration script
├── sidebar.css                   # Sidebar styling
├── popup/                        # Extension popup (settings)
│   ├── popup.html
│   └── popup.js
├── modules/                      # Modular components
│   ├── api-client.js            # External API communications
│   ├── storage-manager.js       # Chrome storage operations
│   └── document-processor.js    # Google Docs DOM manipulation
├── security/                     # Security configuration
│   └── security-config.js       # Security policies & validation
├── SECURITY.md                   # Security documentation
└── README.md                     # This file
```

## Architecture Benefits

### 1. **Modularity**
- **Separation of Concerns**: Each module handles specific functionality
- **Maintainability**: Easier to update and debug individual components
- **Testability**: Modules can be tested independently
- **Reusability**: Components can be reused across different parts of the extension

### 2. **Security**
- **Input Validation**: All user inputs are sanitized and validated
- **Rate Limiting**: Prevents API abuse and excessive requests
- **Secure Storage**: Uses Chrome's encrypted storage APIs
- **CSP Compliance**: Follows Content Security Policy best practices

### 3. **Scalability**
- **Easy Extension**: New features can be added as separate modules
- **Performance**: Modular loading reduces initial bundle size
- **Code Organization**: Clear structure makes onboarding easier

## Module Responsibilities

### API Client (`modules/api-client.js`)
- Google Gemini API integration
- SerpAPI web and scholar search
- API key validation
- Response parsing and error handling

### Storage Manager (`modules/storage-manager.js`)
- Chrome storage API wrapper
- Settings management
- Conversation history persistence
- Data encryption/decryption helpers

### Document Processor (`modules/document-processor.js`)
- Google Docs content extraction
- Document ID parsing
- DOM manipulation for sidebar injection
- Document change application

### Security Config (`security/security-config.js`)
- Input sanitization
- Rate limiting
- API endpoint validation
- Security event logging

## Security Features

✅ **Input Sanitization** - All user inputs are cleaned and validated  
✅ **Rate Limiting** - Prevents API abuse  
✅ **Endpoint Validation** - Only approved APIs can be accessed  
✅ **Secure Storage** - Uses Chrome's encrypted storage  
✅ **CSP Compliance** - Follows security best practices  
✅ **Error Handling** - Secure error messages without data leakage  

## Installation

1. Clone or download the extension files
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable "Developer mode"
4. Click "Load unpacked" and select the `docagent_extension` folder
5. Configure your API keys in the extension popup

## Configuration

### Required API Keys:
- **Google Gemini API Key**: For AI chat functionality
- **SerpAPI Key**: For web and academic search (optional)

### Settings:
- Citation style (APA, MLA, Chicago)
- Sidebar position and width
- Rate limiting preferences

## Usage

1. Open any Google Docs document
2. The DocAgent sidebar will appear automatically
3. Type questions or requests in the chat interface
4. DocAgent will analyze your document and provide contextual responses
5. Accept or reject suggested document changes

## Development

### Adding New Modules:
1. Create new module in `modules/` directory
2. Export class or functions for use
3. Import in `background.js` or `content.js`
4. Update `manifest.json` to include new files

### Security Considerations:
- Always validate inputs using `SecurityConfig`
- Use rate limiting for external API calls
- Follow CSP guidelines for any new code
- Test with various input types and edge cases

## Browser Compatibility

- Chrome 88+ (Manifest V3 support)
- Edge 88+ (Chromium-based)
- Other Chromium-based browsers

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]