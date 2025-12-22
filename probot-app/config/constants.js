// config/constants.js
module.exports = {
  COMMENT_EXPIRY_MINUTES: 2, // Demo: 2 minutes for quick testing
  CLEANUP_INTERVAL_MS: 60 * 1000, // Check every 60 seconds
  
  getBackendUrl: () => {
    return process.env.BACKEND_URL || null;
  }
};