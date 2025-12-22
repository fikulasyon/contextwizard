// handlers/issue-comment.js
const { isFromBot } = require('../utils/bot-detection');
const { parseCommand, isWizardReviewCommand } = require('../utils/command-parser');
const { generateMessageCode, addMessageCodeFooter } = require('../utils/message-code');
const { 
  callBackend, 
  storePendingComment, 
  lookupPendingComment, 
  deletePendingComment 
} = require('../services/backend-api');
const { 
  replyToPrThread, 
  deleteInlineComment, 
  deleteThreadComment 
} = require('../services/github-api');
const { buildIssueCommentPayload, buildWizardReviewPayload } = require('../builders/payload-builder');
const { COMMENT_EXPIRY_MINUTES } = require('../config/constants');

async function handleIssueComment(context) {
  try {
    console.log("=== Received issue_comment.created event ===");
    console.log("Comment body:", context.payload.comment.body);
    
    if (isFromBot(context)) {
      console.log("Skipping: comment is from bot");
      return;
    }

    const commentBody = context.payload.comment.body || "";
    const parsed = parseCommand(commentBody);

    // 1. Handle /accept and /reject commands
    if (parsed) {
      context.log.info({ command: parsed.command, code: parsed.code }, "Processing command");
      
      const pendingComment = await lookupPendingComment(context, parsed.code);
      
      if (!pendingComment) {
        context.log.info({ code: parsed.code }, "Code not found or expired");
        return;
      }

      const { comment_id, comment_type, owner, repo } = pendingComment;
      const commandCommentId = context.payload.comment.id;

      if (parsed.command === "accept") {
        await deletePendingComment(context, parsed.code);
        context.log.info({ code: parsed.code }, "✅ Comment accepted and kept");
        
        // Delete the /accept command itself
        await deleteThreadComment(context, owner, repo, commandCommentId);
        
      } else if (parsed.command === "reject") {
        // Delete the AI comment
        if (comment_type === "inline") {
          await deleteInlineComment(context, owner, repo, comment_id);
        } else {
          await deleteThreadComment(context, owner, repo, comment_id);
        }
        
        await deletePendingComment(context, parsed.code);
        context.log.info({ code: parsed.code }, "✅ Comment rejected and deleted");
        
        // Delete the /reject command itself
        await deleteThreadComment(context, owner, repo, commandCommentId);
      }
      return;
    }

    // 2. Check if it's a /wizard-review command
    if (isWizardReviewCommand(commentBody)) {
      console.log("🧙‍♂️ Detected /wizard-review command");
      
      const issue = context.payload.issue;
      const repo = context.payload.repository;
      
      // Verify this is a PR
      if (!issue.pull_request) {
        context.log.info("Wizard command on regular issue, skipping");
        return;
      }
      
      // Fetch full PR details
      const owner = repo.owner.login;
      const repoName = repo.name;
      const prNumber = issue.number;
      
      const prResponse = await context.octokit.pulls.get({
        owner,
        repo: repoName,
        pull_number: prNumber
      });
      const pr = prResponse.data;
      
      // Build wizard payload
      const payloadForBackend = await buildWizardReviewPayload(context, pr, repo);
      
      // Call backend for wizard review
      const replyBody = await callBackend(context, payloadForBackend);
      if (!replyBody) {
        context.log.error("Wizard review returned no response");
        return;
      }
      
      // Add message code footer for accept/reject
      const messageCode = generateMessageCode();
      const fullReplyBody = addMessageCodeFooter(replyBody, messageCode);
      
      // Post the wizard review as a thread comment
      const postedComment = await replyToPrThread(
        context,
        owner,
        repoName,
        prNumber,
        fullReplyBody
      );
      
      // Store as pending comment
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
      
      context.log.info({ 
        messageCode, 
        commentId: postedComment.id, 
        prNumber 
      }, "🧙‍♂️ Posted wizard review with message code");
      
      return;
    }

    // 3. Regular conversation comment (not a command)
    console.log("Processing as regular conversation comment");
    
    const issue = context.payload.issue;
    const repo = context.payload.repository;
    
    // Check if this is a PR
    if (!issue.pull_request) {
      context.log.info("Comment is on regular issue, skipping");
      return;
    }
    
    const payloadForBackend = await buildIssueCommentPayload(context);
    if (!payloadForBackend) return;
    
    const replyBody = await callBackend(context, payloadForBackend);
    if (!replyBody) return;
    
    const messageCode = generateMessageCode();
    const fullReplyBody = addMessageCodeFooter(replyBody, messageCode);
    
    const owner = payloadForBackend.repo_owner;
    const repoName = payloadForBackend.repo_name;
    const prNumber = payloadForBackend.pr_number;
    
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
    
    context.log.info({ 
      messageCode, 
      commentId: postedComment.id 
    }, "Posted conversation reply with message code");
    
  } catch (err) {
    context.log.error({ err }, "Error in issue_comment.created handler");
    console.error("❌ ERROR:", err);
  }
}

module.exports = { handleIssueComment };