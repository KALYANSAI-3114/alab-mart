/**
 * Alab-Mart API Service
 * Centralized API handler for backend communication
 */

const API_BASE = '';

const API = {
  /**
   * Send audio blob to the backend voice assistant
   * @param {Blob} audioBlob 
   * @param {string} sessionId 
   * @returns {Promise<Object>}
   */
  async sendVoiceCommand(audioBlob, sessionId) {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'speech.wav');
    formData.append('session_id', sessionId);

    try {
      const response = await fetch(`${API_BASE}/assistant/voice`, {
        method: 'POST',
        body: formData
      });
      if (!response.ok) {
        throw new Error(`Voice server error: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('API.sendVoiceCommand error:', error);
      throw error;
    }
  },

  /**
   * Send text command to the assistant endpoint
   * @param {string} command 
   * @param {string} sessionId 
   * @returns {Promise<Object>}
   */
  async sendTextCommand(command, sessionId) {
    try {
      const response = await fetch(`${API_BASE}/assistant/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, session_id: sessionId })
      });
      if (!response.ok) {
        throw new Error(`Command server error: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('API.sendTextCommand error:', error);
      throw error;
    }
  },

  /**
   * Fetch Text-To-Speech audio stream
   * @param {string} text 
   * @returns {Promise<Blob>}
   */
  async getTTSAudio(text) {
    try {
      const response = await fetch(`${API_BASE}/assistant/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      if (!response.ok) {
        throw new Error(`TTS server error: ${response.statusText}`);
      }
      return await response.blob();
    } catch (error) {
      console.error('API.getTTSAudio error:', error);
      throw error;
    }
  },

  /**
   * Fetch products list from database
   * @returns {Promise<Array>}
   */
  async getProducts() {
    try {
      const response = await fetch(`${API_BASE}/api/products`);
      if (!response.ok) {
        throw new Error(`Failed to fetch products`);
      }
      return await response.json();
    } catch (error) {
      console.error('API.getProducts error:', error);
      throw error;
    }
  },

  /**
   * Authenticate User Login
   * @param {string} email
   * @param {string} password
   */
  async login(email, password) {
    const response = await fetch(`${API_BASE}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Login failed');
    }
    return await response.json();
  },

  /**
   * Register User
   * @param {string} email
   * @param {string} password
   */
  async register(email, password) {
    const response = await fetch(`${API_BASE}/api/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Registration failed');
    }
    return await response.json();
  },

  /**
   * Create order during checkout
   * @param {Object} orderData 
   */
  async checkout(orderData) {
    const response = await fetch(`${API_BASE}/api/checkout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(orderData)
    });
    return await response.json();
  }
};