// index.js
const { handleReviewComment } = require('./handlers/review-comment');
const { handleReviewSubmitted } = require('./handlers/review-submitted');
const { handleIssueComment } = require('./handlers/issue-comment');
const { startCleanupJob } = require('./jobs/cleanup');

module.exports = (app) => {
  // Start background cleanup job
  startCleanupJob(app);

  // Register event handlers
  app.on("pull_request_review_comment.created", handleReviewComment);
  app.on("pull_request_review.submitted", handleReviewSubmitted);
  app.on("issue_comment.created", handleIssueComment);
};