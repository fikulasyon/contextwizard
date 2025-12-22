// handlers/review-submitted.js
const { isFromBot } = require('../utils/bot-detection');
const { generateMessageCode, addMessageCodeFooter } = require('../utils/message-code');
const { callBackend, storePendingComment } = require('../services/backend-api');
const { replyToPrThread } = require('../services/github-api');
const { buildReviewPayload } = require('../builders/payload-builder');
const { COMMENT_EXPIRY_MINUTES } = require('../config/constants');

async function handleReviewSubmitted(context) {
  try {
    if (isFromBot(context)) {
      context.log.info("Skipping event from bot sender.");
      return;
    }

    const reviewBody = context.payload.review.body;
    if (!reviewBody || reviewBody.trim() === "") {
      context.log.info("Skipping review with empty body.");
      return;
    }

    const payloadForBackend = await buildReviewPayload(context);
    if (!payloadForBackend) {
      context.log.info("Review payload construction failed, skipping.");
      return;
    }

    // Skip if review has inline comments
    if (payloadForBackend.inline_comment_count > 0) {
      context.log.info(
        { 
          review_id: context.payload.review.id, 
          inline_count: payloadForBackend.inline_comment_count 
        }, 
        "Skipping review with inline comments - inline comments will be handled separately"
      );
      return;
    }

    const replyBody = await callBackend(context, payloadForBackend);
    if (!replyBody) return;

    const messageCode = generateMessageCode();
    const fullReplyBody = addMessageCodeFooter(replyBody, messageCode);

    const repo = context.payload.repository;
    const pr = context.payload.pull_request;
    const owner = repo.owner.login;
    const repoName = repo.name;
    const prNumber = pr.number;

    const postedComment = await replyToPrThread(
      context,
      owner,
      repoName,
      prNumber,
      fullReplyBody
    );

    const expiresAt = Math.floor(Date.now() / 1000) + (COMMENT_EXPIRY_MINUTES * 60);
    await storePendingComment(context, {
      code: messageCode,
      comment_id: postedComment.id,
      comment_type: "thread",
      owner,
      repo: repoName,
      pr_number: prNumber,
      installation_id: context.payload.installation.id,
      expires_at: expiresAt
    });

    context.log.info(
      { pr: prNumber, review_id: context.payload.review.id, messageCode },
      "Replied to submitted review with message code"
    );
  } catch (err) {
    context.log.error({ err }, "Error while handling pull_request_review.submitted");
  }
}

module.exports = { handleReviewSubmitted };