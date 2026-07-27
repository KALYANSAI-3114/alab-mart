/**
 * Alab-Mart AI Voice Assistant UI Controller
 * File: frontend/js/voice/widget.js
 */

// Global Session Key
const SESSION_STORAGE_KEY = 'alab_mart_session_id';

// State Variables
let isRecording = false;
let isProcessing = false;
let conversationHistory = [];

// DOM Element References
let alabPanel = null;
let voiceBtn = null;
let voiceStatus = null;
let transcriptText = null;
let alabMessages = null;

// ==========================================
// 1. SESSION MANAGEMENT
// ==========================================

/**
 * Gets or creates a unique session ID stored in localStorage.
 * @returns {string} Session ID
 */
function getOrCreateSessionId() {
  let sessionId = localStorage.getItem(SESSION_STORAGE_KEY);
  if (!sessionId) {
    sessionId = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }
  return sessionId;
}

// ==========================================
// 2. UI & STATUS CONTROLLER
// ==========================================

/**
 * Toggles the AI Assistant widget panel visibility.
 * Toggles both 'alabPanel' and container 'alabWidget' if available.
 * Automatically focuses input when opened.
 * @param {boolean} show - True to show, false to hide
 */
window.toggleAlabWidget = function (show) {
  const alabWidget = document.getElementById('alabWidget');

  if (show) {
    if (alabPanel) alabPanel.classList.add('open');
    if (alabWidget) alabWidget.classList.add('open');
    if (transcriptText) transcriptText.focus();
  } else {
    if (alabPanel) alabPanel.classList.remove('open');
    if (alabWidget) alabWidget.classList.remove('open');
  }
};

/**
 * Updates the voice status label UI.
 * @param {string} statusText - Status message to render
 */
function updateStatus(statusText) {
  if (voiceStatus) {
    voiceStatus.textContent = statusText;
  }
}

/**
 * Enables or disables UI controls to prevent duplicate submissions.
 * @param {boolean} disabled - True to disable controls
 */
function setControlsDisabled(disabled) {
  isProcessing = disabled;
  if (voiceBtn) voiceBtn.disabled = disabled;
  if (transcriptText) transcriptText.disabled = disabled;
}

/**
 * Appends a message bubble to the chat container and auto-scrolls to bottom.
 * Uses textContent and whiteSpace pre-wrap for safe rendering & line break preservation.
 * @param {string} text - Message content
 * @param {'user' | 'ai'} sender - Message sender type
 */
function appendMessage(text, sender) {
  if (!alabMessages || !text) return;

  const msgDiv = document.createElement('div');
  msgDiv.className = sender === 'user' ? 'alab-message-user' : 'alab-message-ai';
  msgDiv.textContent = text;
  msgDiv.style.whiteSpace = 'pre-wrap';

  alabMessages.appendChild(msgDiv);
  alabMessages.scrollTop = alabMessages.scrollHeight;
}

// ==========================================
// 3. BACKEND RESPONSE PROCESSOR
// ==========================================

/**
 * Processes backend responses (Message display, History tracking, Cart syncing, TTS playback).
 * @param {Object} data - Backend JSON response
 */
async function handleBackendResponse(data) {
  // Extract reply from variable possible payload keys
  const reply = data?.reply || "";
  if (reply) {
    // Append AI reply to Chat UI
    appendMessage(reply, 'ai');

    // Track AI conversation history
    conversationHistory.push({
      role: 'assistant',
      content: reply
    });

    // Play TTS Audio and wait until finished before updating status to "Ready"
    try {
      updateStatus('Speaking...');
      const audioBlob = await API.getTTSAudio(reply);
      if (audioBlob && window.speechHandler && typeof window.speechHandler.playAudio === 'function') {
        await window.speechHandler.playAudio(audioBlob);
      }
    } catch (error) {
      console.warn('TTS playback failed or skipped:', error);
    }
  }

  // Handle cart synchronization cleanly if array exists
  if (Array.isArray(data?.cart) && window.storeApp && typeof window.storeApp.syncCart === 'function') {
    window.storeApp.syncCart(data.cart);
  }

  if (data?.checkout && window.storeApp) {
    window.storeApp.checkout();
  }

  updateStatus('Ready');
}

// ==========================================
// 4. VOICE RECORDING & HANDLERS
// ==========================================

/**
 * Handles completion of speech recording when silence is detected or manually stopped.
 * Safely wraps stopRecording() in a try-catch block.
 */
async function handleSilenceDetected() {
  if (!isRecording) return;
  isRecording = false;

  setControlsDisabled(true);

  if (!window.speechHandler || typeof window.speechHandler.stopRecording !== 'function') {
    setControlsDisabled(false);
    updateStatus('Error');
    appendMessage('Speech handler not initialized.', 'ai');
    return;
  }

  let audioBlob = null;
  try {
    audioBlob = await window.speechHandler.stopRecording();
  } catch (err) {
    console.error('Stop recording failed:', err);
    setControlsDisabled(false);
    updateStatus('Error');
    appendMessage('Failed to stop recording.', 'ai');
    return;
  }

  if (voiceBtn) {
    voiceBtn.textContent = 'Speak';
    voiceBtn.classList.remove('listening');
  }

  if (!audioBlob) {
    setControlsDisabled(false);
    updateStatus('Error');
    appendMessage('No audio recorded.', 'ai');
    return;
  }

  updateStatus('Processing...');

  let data = null;
  try {
    const sessionId = getOrCreateSessionId();
    data = await API.sendVoiceCommand(audioBlob, sessionId);

    if (data) {
      const userText = data.transcription || data.user_text;
      if (userText) {
        appendMessage(userText, 'user');
        conversationHistory.push({
          role: 'user',
          content: userText
        });
      }
      await handleBackendResponse(data);
    } else {
      updateStatus('Error');
      appendMessage('Server returned empty response.', 'ai');
    }
  } catch (error) {
    console.error('Voice command error:', error);
    updateStatus('Error');
    appendMessage('Server unavailable.', 'ai');
  } finally {
    setControlsDisabled(false);

    if (voiceBtn) {
      voiceBtn.classList.remove("listening");
    }

    if (
    data?.listen_again &&
    alabPanel &&
    alabPanel.classList.contains("open")
) {
    setTimeout(() => {
        handleVoiceButtonClick();
    }, 700);
}
  }
}

/**
 * Handles Speak button clicks with debouncing and recording control.
 */
async function handleVoiceButtonClick() {
  if (isProcessing) return;

  if (isRecording) {
    // Manually stop and trigger processing
    await handleSilenceDetected();
  } else {
    // Check speechHandler presence before recording
    if (!window.speechHandler || typeof window.speechHandler.startRecording !== 'function') {
      updateStatus('Error');
      appendMessage('Speech handler not initialized.', 'ai');
      return;
    }

    // Start recording audio
    try {
      updateStatus('🎤 Listening...');

      if (voiceBtn) {
        voiceBtn.textContent = 'Listening...';
        voiceBtn.classList.add('listening');
      }

      isRecording = true;

      await window.speechHandler.startRecording(handleSilenceDetected);
    } catch (error) {
      isRecording = false;

      if (voiceBtn) {
        voiceBtn.textContent = 'Speak';
        voiceBtn.classList.remove('listening');
      }

      if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        updateStatus('Error');
        appendMessage('Microphone permission denied.', 'ai');
      } else {
        updateStatus('Error');
        appendMessage('Could not access microphone.', 'ai');
      }
    }
  }
}

// ==========================================
// 5. TEXT COMMAND HANDLER
// ==========================================

/**
 * Handles text input submission.
 * Ignores empty/whitespace inputs and maintains auto-focus.
 */
window.runTypedVoiceCommand = async function () {
  if (!transcriptText || isProcessing) return;

  const text = transcriptText.value.trim();
  if (!text) return;

  // Clear input box and reset focus
  transcriptText.value = '';
  transcriptText.focus();

  // Append user message to UI and history
  appendMessage(text, 'user');
  conversationHistory.push({
    role: 'user',
    content: text
  });

  setControlsDisabled(true);
  updateStatus('Processing...');

  try {
    const sessionId = getOrCreateSessionId();
    const data = await API.sendTextCommand(text, sessionId);

    if (data) {
      await handleBackendResponse(data);
    } else {
      updateStatus('Error');
      appendMessage('Server returned empty response.', 'ai');
    }
  } catch (error) {
    console.error('Text command error:', error);
    updateStatus('Error');
    appendMessage('Server unavailable.', 'ai');
  } finally {
    setControlsDisabled(false);
  }
};

// ==========================================
// 6. INITIALIZATION & EVENT LISTENERS
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
  // Capture DOM elements
  alabPanel = document.getElementById('alabPanel');
  voiceBtn = document.getElementById('voiceBtn');
  voiceStatus = document.getElementById('voiceStatus');
  transcriptText = document.getElementById('transcriptText');
  alabMessages = document.getElementById('alabMessages');

  const alabLauncher = document.getElementById('alabLauncher');

  // Event Listener: Launcher Toggle
  if (alabLauncher) {
    alabLauncher.addEventListener('click', () => {
      const isOpen = alabPanel ? alabPanel.classList.contains('open') : false;
      window.toggleAlabWidget(!isOpen);
    });
  }

  // Event Listener: Voice Button
  if (voiceBtn) {
    voiceBtn.addEventListener('click', handleVoiceButtonClick);
  }

  // Event Listener: Keyboard Enter key on text input
  if (transcriptText) {
    transcriptText.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        window.runTypedVoiceCommand();
      }
    });
  }

  // Ensure initial session key exists
  getOrCreateSessionId();

  // Initial Status State
  updateStatus('Ready');
});