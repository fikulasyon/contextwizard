// handlers/review-comment.js
const { isFromBot } = require('../utils/bot-detection');
const { isWizardReviewCommand } = require('../utils/command-parser');
const { generateMessageCode, addMessageCodeFooter } = require('../utils/message-code');
const { callBackend, storePendingComment } = require('../services/backend-api');
const { replyToInlineComment } = require('../services/github-api');
const { buildReviewCommentPayload, buildWizardReviewPayload } = require('../builders/payload-builder');
const { COMMENT_EXPIRY_MINUTES } = require('../config/constants');

async function handleReviewComment(context) {
  try {
    console.log("Received pull_request_review_comment.created event");
    
    if (isFromBot(context)) return;

    const commentBody = (context.payload.comment.body || "").trim();
    
    // Check for wizard command in inline comment
    if (isWizardReviewCommand(commentBody)) {
      console.log("🧙‍♂️ Detected /wizard-review in inline comment");
      
      const repo = context.payload.repository;
      const pr = context.payload.pull_request;
      
      const payloadForBackend = await buildWizardReviewPayload(context, pr, repo);
      
      const replyBody = await callBackend(context, payloadForBackend);
      if (!replyBody) return;
      
      const messageCode = generateMessageCode();
      const fullReplyBody = addMessageCodeFooter(replyBody, messageCode);
      
      const owner = repo.owner.login;
      const repoName = repo.name;
      const prNumber = pr.number;
      
      // Reply to the inline comment that triggered wizard
      const postedComment = await replyToInlineComment(
        context,
        owner,
        repoName,
        prNumber,
        context.payload.comment.id,
        fullReplyBody
      );
      
      const expiresAt = Math.floor(Date.now() / 1000) + (COMMENT_EXPIRY_MINUTES * 60);
      await storePendingComment(context, {
        code: messageCode,
        comment_id: postedComment.id,
        comment_type: "inline",
        owner,
        repo: repoName,
        pr_number: prNumber,
        installation_id: context.payload.installation.id,
        expires_at: expiresAt
      });
      
      context.log.info({ messageCode }, "🧙‍♂️ Posted inline wizard review");
      return;
    }
    
    // Regular inline comment processing
    const payloadForBackend = await buildReviewCommentPayload(context);
    if (!payloadForBackend) return;
    
    const replyBody = await callBackend(context, payloadForBackend);
    if (!replyBody) return;
    
    const messageCode = generateMessageCode();
    const fullReplyBody = addMessageCodeFooter(replyBody, messageCode);
    
    const owner = payloadForBackend.repo_owner;
    const repoName = payloadForBackend.repo_name;
    const prNumber = payloadForBackend.pr_number;
    
    const postedComment = await replyToInlineComment(
      context,
      owner,
      repoName,
      prNumber,
      context.payload.comment.id,
      fullReplyBody
    );
    
    const expiresAt = Math.floor(Date.now() / 1000) + (COMMENT_EXPIRY_MINUTES * 60);
    await storePendingComment(context, {
      code: messageCode,
      comment_id: postedComment.id,
      comment_type: "inline",
      owner,
      repo: repoName,
      pr_number: prNumber,
      installation_id: context.payload.installation.id,
      expires_at: expiresAt
    });
    
    context.log.info({ messageCode }, "Posted inline comment reply");
    
  } catch (err) {
    context.log.error({ err }, "Error in pull_request_review_comment.created");
  }
}

module.exports = { handleReviewComment };