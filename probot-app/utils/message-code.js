// utils/message-code.js
const { COMMENT_EXPIRY_MINUTES } = require('../config/constants');

function generateMessageCode() {
  // Generate 6-character alphanumeric code (uppercase)
  return Math.random().toString(36).substring(2, 8).toUpperCase();
}

function addMessageCodeFooter(commentBody, messageCode) {
  return `${commentBody}\n\n---\n_Message ID: **${messageCode}** • Reply with \`/accept ${messageCode}\` or \`/reject ${messageCode}\` within ${COMMENT_EXPIRY_MINUTES} minutes_`;
}

module.exports = { 
  generateMessageCode, 
  addMessageCodeFooter 
};