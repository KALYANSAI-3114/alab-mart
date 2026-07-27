const BACKEND_API_URL = "/api/chat";

const messagesContainer = document.getElementById('messagesContainer');
const userInput = document.getElementById('userInput');

// Auto-expand textarea on input
userInput.addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = (this.scrollHeight) + 'px';
});

// Submit on Enter key (Shift+Enter for newline)
function handleKeyDown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage(event);
  }
}

async function sendMessage(event) {
  if (event) event.preventDefault();
  
  const text = userInput.value.trim();
  if (!text) return;

  // 1. Display User Message
  appendMessage('user', text);
  userInput.value = '';
  userInput.style.height = 'auto';

  // 2. Add temporary loading placeholder for Assistant
  const loadingId = appendLoadingMessage();

  try {
    // 3. Send request to FastAPI RAG Endpoint
    const response = await fetch(BACKEND_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ query: text })
    });

    const data = await response.json();
    
    // Remove loading indicator
    removeMessage(loadingId);

    // 4. Render RAG Assistant Response
    if (data && data.response) {
      appendMessage('assistant', data.response);
    } else {
      appendMessage('assistant', "I received your query, but no response text was returned.");
    }

  } catch (error) {
    console.error("Error communicating with RAG backend:", error);
    removeMessage(loadingId);
    appendMessage('assistant', "Sorry, I am having trouble connecting to the backend server.");
  }
}

function appendMessage(role, text) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${role}-message`;

  const isUser = role === 'user';
  const avatarClass = isUser ? 'user-avatar' : 'ai-avatar';
  const avatarText = isUser ? 'You' : 'AI';

  messageDiv.innerHTML = `
    <div class="avatar ${avatarClass}">${avatarText}</div>
    <div class="message-content">
      <p>${escapeHtml(text).replace(/\n/g, '<br>')}</p>
    </div>
  `;

  messagesContainer.appendChild(messageDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
  return messageDiv;
}

function appendLoadingMessage() {
  const id = 'loading-' + Date.now();
  const messageDiv = document.createElement('div');
  messageDiv.id = id;
  messageDiv.className = 'message assistant-message';

  messageDiv.innerHTML = `
    <div class="avatar ai-avatar">AI</div>
    <div class="message-content">
      <p><em>Thinking and retrieving relevant information...</em></p>
    </div>
  `;

  messagesContainer.appendChild(messageDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
  return id;
}

function removeMessage(id) {
  const element = document.getElementById(id);
  if (element) {
    element.remove();
  }
}

function startNewChat() {
  messagesContainer.innerHTML = `
    <div class="message assistant-message">
      <div class="avatar ai-avatar">AI</div>
      <div class="message-content">
        <p>New session started! What would you like to ask about Alabmart?</p>
      </div>
    </div>
  `;
}

function escapeHtml(string) {
  return String(string).replace(/[&<>"']/g, function(s) {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[s];
  });
}
