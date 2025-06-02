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
  
  // Track conversation ID for history
  let currentConversationId = null;
  let currentPdfFile = null;  // Store the selected PDF file
  
  // Function to add a message to the chat
  function addMessage(message, sender) {
      // Remove centered content when first message is sent
      if (centeredContent && mainContent.contains(centeredContent)) {
          mainContent.removeChild(centeredContent);
          
          // Create chat container if it doesn't exist
          if (!document.querySelector('.chat-container')) {
              const chatContainer = document.createElement('div');
              chatContainer.className = 'chat-container';
              mainContent.appendChild(chatContainer);
              
              // Add styles for the chat container
              const style = document.createElement('style');
              style.textContent = `
                  .chat-container {
                      width: 100%;
                      max-width: 800px;
                      margin: 0 auto;
                      padding: 1rem;
                      overflow-y: auto;
                      height: 100%;
                      display: flex;
                      flex-direction: column;
                  }
                  
                  .message {
                      padding: 0.75rem 1rem;
                      margin-bottom: 1rem;
                      border-radius: 8px;
                      max-width: 80%;
                  }
                  
                  .user-message {
                      background-color: #2b2b2b;
                      align-self: flex-end;
                  }
                  
                  .bot-message {
                      background-color: #1e1e1e;
                      border: 1px solid #333;
                      align-self: flex-start;
                      white-space: pre-wrap;
                  }

                  .typing-indicator {
                      display: flex;
                      align-items: center;
                      padding: 0.75rem 1rem;
                      margin-bottom: 1rem;
                      border-radius: 8px;
                      background-color: #1e1e1e;
                      border: 1px solid #333;
                      align-self: flex-start;
                  }
                  
                  .typing-dot {
                      width: 8px;
                      height: 8px;
                      margin: 0 2px;
                      background-color: #666;
                      border-radius: 50%;
                      opacity: 0.6;
                      animation: typing-dot 1.4s infinite ease-in-out;
                  }
                  
                  .typing-dot:nth-child(1) { animation-delay: 0s; }
                  .typing-dot:nth-child(2) { animation-delay: 0.2s; }
                  .typing-dot:nth-child(3) { animation-delay: 0.4s; }
                  
                  @keyframes typing-dot {
                      0%, 60%, 100% { transform: translateY(0); }
                      30% { transform: translateY(-5px); }
                  }
                  
                  .message-with-pdf {
                      position: relative;
                  }
                  
                  .pdf-badge {
                      display: inline-block;
                      background-color: #444;
                      color: #fff;
                      padding: 2px 6px;
                      border-radius: 4px;
                      font-size: 0.8rem;
                      margin-bottom: 5px;
                  }
                  
                  .pdf-badge i {
                      margin-right: 4px;
                  }
              `;
              document.head.appendChild(style);
          }
      }
      
      // Create message element
      const messageElement = document.createElement('div');
      messageElement.className = `message ${sender}-message`;
      
      // Add PDF badge if this is a user message with a PDF
      if (sender === 'user' && currentPdfFile) {
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
      
      try {
          // Create form data for the API request
          const formData = new FormData();
          formData.append('message', message);
          
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

  // Initialize UI and event listeners
  function initializeUI() {
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
      
      // Quick Settings dropdown (if needed for other features)
      const dropdownButton = document.querySelector('.dropdown-button');
      if (dropdownButton) {
          dropdownButton.addEventListener('click', function() {
              // Implement dropdown functionality if needed
              console.log('Settings dropdown clicked');
          });
      }
  }
  
  // Initialize everything
  initializeUI();
});