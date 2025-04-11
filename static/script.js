document.addEventListener('DOMContentLoaded', function() {
  // Get DOM elements
  const chatInput = document.querySelector('.chat-input');
  const sendButton = document.querySelector('.send-button');
  const mainContent = document.querySelector('main');
  const centeredContent = document.querySelector('.centered-content');
  const pdfUpload = document.getElementById('pdf-upload');
  const pdfIndicator = document.querySelector('.pdf-indicator');
  const pdfName = document.querySelector('.pdf-name');
  const removePdfButton = document.querySelector('.remove-pdf');
  const languageModal = document.querySelector('.language-modal');
  const languageSettingsButton = document.querySelector('.language-settings-button');
  const closeModalButton = document.querySelector('.close-modal');
  const languageOptions = document.querySelectorAll('.language-option');
  const currentLanguageLabels = document.querySelectorAll('.current-language');
  
  // Track conversation ID for history
  let currentConversationId = null;
  let currentModel = 'llama3-70b';  // Default model
  let currentPdfFile = null;  // Store the selected PDF file
  let currentLanguage = 'en';  // Default language is English
  
  // Language names mapping
  const languageNames = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'ja': 'Japanese',
    'zh': 'Chinese',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ar': 'Arabic',
    'hi': 'Hindi'
  };
  
  // Function to add a message to the chat
  function addMessage(message, sender, isSystem = false) {
      // Remove centered content when first message is sent
      if (centeredContent && mainContent.contains(centeredContent)) {
          mainContent.removeChild(centeredContent);
          
          // Create chat container if it doesn't exist
          if (!document.querySelector('.chat-container')) {
              const chatContainer = document.createElement('div');
              chatContainer.className = 'chat-container';
              mainContent.appendChild(chatContainer);
          }
      }
      
      // Create message element
      const messageElement = document.createElement('div');
      
      if (isSystem) {
          messageElement.className = 'system-message';
      } else {
          messageElement.className = `message ${sender}-message`;
      }
      
      // Add PDF badge if this is a user message with a PDF
      if (sender === 'user' && currentPdfFile && !isSystem) {
          messageElement.classList.add('message-with-pdf');
          
          const pdfBadge = document.createElement('div');
          pdfBadge.className = 'pdf-badge';
          pdfBadge.innerHTML = `<i class="fas fa-file-pdf"></i> ${currentPdfFile.name}`;
          
          messageElement.appendChild(pdfBadge);
          
          // Add a container for the message text
          const textContainer = document.createElement('div');
          textContainer.textContent = message;
          messageElement.appendChild(textContainer);
      } else {
          messageElement.textContent = message;
      }
      
      // Add message to chat
      document.querySelector('.chat-container').appendChild(messageElement);
      
      // Scroll to bottom
      mainContent.scrollTop = mainContent.scrollHeight;
      
      return messageElement;
  }
  
  // Function to show typing indicator
  function showTypingIndicator() {
      const container = document.querySelector('.chat-container');
      if (!container) return null;
      
      const indicator = document.createElement('div');
      indicator.className = 'typing-indicator';
      
      for (let i = 0; i < 3; i++) {
          const dot = document.createElement('div');
          dot.className = 'typing-dot';
          indicator.appendChild(dot);
      }
      
      container.appendChild(indicator);
      mainContent.scrollTop = mainContent.scrollHeight;
      
      return indicator;
  }
  
  // Function to check if message contains language change request
  function containsLanguageChangeRequest(message) {
      const languageChangeKeywords = [
          "speak in", "talk in", "reply in", "respond in", 
          "use", "switch to", "change to", "change language to",
          "habla en", "parle en", "sprich in", "parla in"
      ];
      
      return languageChangeKeywords.some(keyword => 
          message.toLowerCase().includes(keyword.toLowerCase())
      );
  }
  
  // Function to update UI language indicators
  function updateLanguageUI(langCode) {
      currentLanguage = langCode;
      const langName = languageNames[langCode] || langCode;
      
      // Update all current language labels
      currentLanguageLabels.forEach(label => {
          label.textContent = langName + (langCode === 'en' ? ' (Default)' : '');
      });
      
      // Update active state in language options
      languageOptions.forEach(option => {
          if (option.getAttribute('data-lang') === langCode) {
              option.classList.add('active');
          } else {
              option.classList.remove('active');
          }
      });
  }
  
  // Send message function
  async function sendMessage() {
      const message = chatInput.value.trim();
      if (!message) return;
      
      // Add user message to chat
      addMessage(message, 'user');
      
      // Clear input after sending
      chatInput.value = '';
      
      // Show typing indicator
      const typingIndicator = showTypingIndicator();
      
      // Check if this is potentially a language change request
      const isLanguageRequest = containsLanguageChangeRequest(message);
      
      try {
          // Create form data for the API request
          const formData = new FormData();
          formData.append('message', message);
          formData.append('model_id', currentModel);
          
          // Include conversation ID if we have one
          if (currentConversationId) {
              formData.append('conversation_id', currentConversationId);
          }
          
          // Add PDF file if selected
          if (currentPdfFile) {
              formData.append('pdf', currentPdfFile);
          }
          
          // Make API request to the backend
          const response = await fetch('/chat', {
              method: 'POST',
              body: formData
          });
          
          // Remove typing indicator
          if (typingIndicator) {
              typingIndicator.remove();
          }
          
          if (!response.ok) {
              throw new Error(`Error: ${response.status}`);
          }
          
          const data = await response.json();
          
          // Save conversation ID if returned
          if (data.conversation_id) {
              currentConversationId = data.conversation_id;
          }
          
          // Check if language was changed
          if (data.preferred_language && data.preferred_language !== currentLanguage) {
              // Add system message about language change
              const langName = languageNames[data.preferred_language] || data.preferred_language;
              addMessage(`Language changed to ${langName}`, 'system', true);
              
              // Update UI
              updateLanguageUI(data.preferred_language);
          }
          
          // Add bot response to chat
          addMessage(data.response, 'bot');
          
          // Clear PDF after sending
          clearPdfSelection();
          
      } catch (error) {
          console.error('Error sending message:', error);
          
          // Remove typing indicator
          if (typingIndicator) {
              typingIndicator.remove();
          }
          
          // Show error message
          addMessage(`Sorry, there was an error processing your request: ${error.message}`, 'bot');
      }
  }
  
  // Function to handle PDF file selection
  function handlePdfSelection(event) {
      const file = event.target.files[0];
      if (file && file.type === 'application/pdf') {
          currentPdfFile = file;
          pdfName.textContent = file.name;
          pdfIndicator.style.display = 'flex';
      }
  }
  
  // Function to clear PDF selection
  function clearPdfSelection() {
      currentPdfFile = null;
      pdfUpload.value = '';
      pdfIndicator.style.display = 'none';
  }
  
  // Function to change language via API
  async function changeLanguage(langCode) {
      // Only make API call if we have a conversation already
      if (currentConversationId) {
          try {
              const formData = new FormData();
              formData.append('language_code', langCode);
              
              const response = await fetch(`/conversations/${currentConversationId}/language`, {
                  method: 'PUT',
                  body: formData
              });
              
              if (!response.ok) {
                  throw new Error(`Error: ${response.status}`);
              }
              
              const data = await response.json();
              
              if (data.success) {
                  // Add system message about language change
                  const langName = languageNames[langCode] || langCode;
                  addMessage(`Language changed to ${langName}`, 'system', true);
              }
          } catch (error) {
              console.error('Error changing language:', error);
              addMessage(`Failed to change language: ${error.message}`, 'system', true);
          }
      }
      
      // Update UI regardless of API call
      updateLanguageUI(langCode);
      
      // Close modal
      languageModal.style.display = 'none';
  }

  // Initialize UI and event listeners
  function initializeUI() {
      // Load available models
      fetch('/models')
          .then(response => response.json())
          .then(data => {
              const models = data.models || {};
              console.log('Available models:', models);
              
              // Set up model selector if needed
              // This would be expanded for a proper UI with model switching
          })
          .catch(error => console.error('Error loading models:', error));
      
      // Event listeners for sending messages
      sendButton.addEventListener('click', sendMessage);
      
      chatInput.addEventListener('keypress', function(e) {
          if (e.key === 'Enter') {
              sendMessage();
          }
      });
      
      // PDF upload handling
      pdfUpload.addEventListener('change', handlePdfSelection);
      removePdfButton.addEventListener('click', clearPdfSelection);
      
      // Language modal
      languageSettingsButton.addEventListener('click', function() {
          languageModal.style.display = 'block';
      });
      
      closeModalButton.addEventListener('click', function() {
          languageModal.style.display = 'none';
      });
      
      // Close modal when clicking outside
      window.addEventListener('click', function(event) {
          if (event.target === languageModal) {
              languageModal.style.display = 'none';
          }
      });
      
      // Language option buttons
      languageOptions.forEach(option => {
          option.addEventListener('click', function() {
              const langCode = this.getAttribute('data-lang');
              changeLanguage(langCode);
          });
      });
      
      // Mark English as active by default
      document.querySelector('.language-option[data-lang="en"]').classList.add('active');
      
      // Quick Settings dropdown
      const dropdownButton = document.querySelector('.dropdown-button');
      if (dropdownButton) {
          dropdownButton.addEventListener('click', function() {
              const dropdownContent = document.querySelector('.dropdown-content');
              dropdownContent.style.display = dropdownContent.style.display === 'block' ? 'none' : 'block';
          });
      }
      
      // Model selector
      const modelSelector = document.querySelector('.model-selector');
      if (modelSelector) {
          modelSelector.addEventListener('click', function() {
              // This would be expanded for a proper model switching UI
              console.log('Model selector clicked');
          });
      }
  }
  
  // Initialize everything
  initializeUI();
});
