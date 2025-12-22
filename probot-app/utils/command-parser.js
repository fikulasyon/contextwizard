// utils/command-parser.js
function parseCommand(commentBody) {
  const trimmed = (commentBody || "").trim();
  
  // Match /accept CODE or /reject CODE
  const acceptMatch = trimmed.match(/^\/accept\s+([A-Z0-9]{6})$/i);
  if (acceptMatch) {
    return { command: "accept", code: acceptMatch[1].toUpperCase() };
  }

  const rejectMatch = trimmed.match(/^\/reject\s+([A-Z0-9]{6})$/i);
  if (rejectMatch) {
    return { command: "reject", code: rejectMatch[1].toUpperCase() };
  }

  return null;
}

function isWizardReviewCommand(commentBody) {
  const trimmed = (commentBody || "").trim();
  return trimmed === "/wizard-review" || trimmed.startsWith("/wizard-review ");
}

module.exports = { 
  parseCommand, 
  isWizardReviewCommand 
};