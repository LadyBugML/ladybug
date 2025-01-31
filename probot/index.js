/**
 * This is the main entrypoint to your Probot app
 * @param {import('probot').Probot} app
 */

import {sendRepo} from './components/sendRepo.js';
import {sendRatings} from './components/sendRatings.js';
import { sendTrace } from './components/sendTrace.js';
import axios from "axios";
import express from "express";
import dotenv from "dotenv";
// At the top of your file, initialize the map
let API_URL = process.env.API_URL;
console.log("API_URL", API_URL);

export default (app, {getRouter}) => {
    const router = getRouter("/");
    const repoToInstallationMap = new Map();
    // Use any middleware
    router.use(express.static("public"));
    router.use(express.json());

    router.post('/post-message', async (req, res) => {
    const { owner, repo, comment_id, message } = req.body;

    if (!owner || !repo || !comment_id || !message) {
        return res.status(400).json({ error: 'Missing required fields: owner, repo, comment_id, message' });
    }

    const repoKey = `${owner}/${repo}`;
    const installationId = repoToInstallationMap.get(repoKey);

    if (!installationId) {
        return res.status(400).json({ error: `Installation not found for repository ${repoKey}` });
    }

    try {
        // Authenticate as the installation
        const octokit = await app.auth(installationId);
        if(!octokit)
            res.status(500).json({error: `Failed to initialize octokit`})

        // Post the comment to the specified issue
        await octokit.issues.updateComment({
            owner,
            repo,
            comment_id,
            body: message,
        });

        console.log(`Posted message to ${repoKey} Issue #${comment_id}: ${message}`);
        return res.status(200).json({ status: 'Comment posted successfully' });
    } catch (error) {
        console.error('Error posting comment:', error);
        return res.status(500).json({ error: 'Failed to post comment' });
    }
});


    app.on("installation_repositories.added", async (context) => {
    const { repositories_added } = context.payload;
    const installationId = context.payload.installation.id;

    try {
        for (const repo of repositories_added) {
            const [ownerName, repoName] = repo.full_name.split('/');
            const repoKey = `${ownerName}/${repoName}`;
            repoToInstallationMap.set(repoKey, installationId);
            console.log("Current repoToInstallationMap:", Array.from(repoToInstallationMap.entries()));

            // Fetch the full repository data
            const { data: fullRepo } = await context.octokit.repos.get({
                owner: ownerName,
                repo: repoName,
            });

            // Create an initial issue
            const initIssue = await context.octokit.issues.create({
                owner: ownerName,
                repo: repoName,
                title: 'Welcome to LadyBug! 🐞',
                body: getInitializationComment(repoName),
            });

            // Create an initial comment on the issue
            const initComment = await context.octokit.issues.createComment({
                owner: ownerName,
                repo: repoName,
                issue_number: initIssue.data.number,
                body: getInitializationComment(repoName),
            });

            // Store the actual comment ID
            const comment_id = initComment.data.id;

            // Pass the full repository object and context to sendRepo
            const repoData = await sendRepo(fullRepo, context);
            if (!repoData) {
                console.error(`sendRepo returned null for ${ownerName}/${repoName}. Skipping Axios POST.`);
                return;
            }

            const data = {
                repoData,
                comment_id
            };

            try {
                const flaskResponse = await axios.post(`${API_URL}/initialization`, data, {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                });
                if (flaskResponse.status !== 200) {
                    throw new Error(`Failed to send data to Flask backend: ${flaskResponse.status} ${flaskResponse.statusText}`);
                }
                console.log('Repo info sent to Flask backend successfully.');

                await context.octokit.issues.createComment({
                    owner: ownerName,
                    repo: repoName,
                    issue_number: initIssue.data.number,
                    body: getCompletionComment(repoName)
                });
            } catch (error) {
                console.error('Error while sending repo info:', error);
            }
        }
    } catch (error) {
        console.error('Failed to process repositories:', error);
    }
});

    app.on('issues.opened', async (context) => {
        const issue = context.payload.issue;
        const repository = context.payload.repository;
        const installationId = context.payload.installation.id;

        console.log(`Issue #${issue.number} opened in repository ${repository.full_name}`);

        const issueAuthor = issue.user;
        if (issueAuthor.type === 'Bot') {
            console.log(`Issue #${issue.number} opened by a bot (${issueAuthor.login}). Ignoring.`);
            return; // Exit early if the issue was opened by a bot
        }

        // Prepare data to send to Flask backend
        const issueBody = issue.body || issue.title;

        repoToInstallationMap.set(repository.full_name, installationId);
        console.log("Current repoToInstallationMap:", Array.from(repoToInstallationMap.entries()));
        try {
            // Fetch the full repository data to ensure all necessary fields are present
            const {data: fullRepo} = await context.octokit.repos.get({
                owner: repository.owner.login,
                repo: repository.name,
            });

            // Pass the full repository object and context to sendRepo
            const repoData = await sendRepo(fullRepo, context);

            if (!repoData) {
                console.error(`sendRepo returned null for ${repository.full_name}. Skipping Axios POST.`);
                // Reply to the issue with an error message
                await replyWithError(context, issue.number, "An error occurred while processing the repository data.");
                return; // Return early if repoData is null
            }

            // Create initial comment
            const initialCommentBody = 'Processing your request... [0%]';
            let initialComment;
            try {
                initialComment = await context.octokit.issues.createComment({
                    owner: repository.owner.login,
                    repo: repository.name,
                    issue_number: issue.number,
                    body: initialCommentBody,
                });
                console.log(`Created initial comment with ID ${initialComment.data.id}`);
            } catch (error) {
                console.error('Error creating initial comment:', error.message);
                return; // Exit if we can't create the initial comment
            }
            // Store the comment ID
            const comment_id = initialComment.data.id;

            // Get the attachment JSON data
            const trace = await sendTrace(issue.body, context);
            if(!trace){
                console.error(`sendTrace returned null for ${issue.number}.`);
            }
         
            const fullData = {
                issue: issueBody,
                repository: repoData,
                trace: trace,
                comment_id
            };

            try {
                const flaskResponse = await axios.post(`${API_URL}/report`, fullData, {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                });

                if (flaskResponse.status !== 200) {
                    throw new Error(`Failed to send data to Flask backend: ${flaskResponse.status} ${flaskResponse.statusText}`);
                }

                // Await sendRatings to handle potential errors
                await sendRatings(flaskResponse.data, context);

            } catch (error) {
                console.error('Error while sending repo info from issues.opened:', error.message);
                // Reply to the issue with an error message
                await replyWithError(context, issue.number, "An error occurred while communicating with the analysis backend.");
            }

        } catch (error) {
            console.error(`Failed to fetch repository data for ${repository.full_name}:`, error.message);
            // Reply to the issue with an error message
            await replyWithError(context, issue.number, "An error occurred while fetching repository data.");
        }
    });

    /**
     * Replies to the issue with an error message.
     *
     * @param {Object} context - The Probot context object.
     * @param {number} issueNumber - The issue number to reply to.
     * @param {string} errorMessage - The error message to include in the comment.
     */
    const replyWithError = async (context, issueNumber, errorMessage) => {
        const commentBody = `Hello! Unfortunately, ${errorMessage} Please try again later or contact support if the issue persists.`;

        const issueComment = context.issue({body: commentBody, issue_number: issueNumber});

        try {
            await context.octokit.issues.createComment(issueComment);
            console.log(`Posted error message to issue #${issueNumber}.`);
        } catch (error) {
            console.error('Failed to post error message to issue:', error.message);
        }
    };

    function getInitializationComment(repoName) {
        return `
# Hang Tight, We're Getting Ready! ⏳ 

Hello, ${repoName}!

I've been invited to your repository, and I'm thrilled to get started! 🎉 I'm currently working behind the scenes to process your codebase and prepare everything I need to assist you with bug localization. 

Initialization might take a few minutes, so hang tight while I set things up. Here's what I'm doing:
- 🪄 Preprocessing all source code files.
- 🔍 Generating embeddings for smarter bug tracking.
- 🔄 Setting up my internal database for your repo.

I'll let you know as soon as the setup is complete with a follow-up comment below. Thank you for your patience!
`;
    }

    function getCompletionComment(repoName) {
        return `
# All Set! 🎉

Good news, ${repoName}! 🥳 

The initialization process is now complete, and I'm ready to assist you with your bug localization needs. Here's what I've done:
- ✅ Successfully preprocessed all source code files.
- ✅ Generated embeddings for better bug analysis.
- ✅ Fully integrated with your repository.

To get assistance localizing bugs, create a new issue and I will automatically take a look.

I'm here to help you save time and debug smarter. Let the journey to cleaner code begin! 🚀

---

Happy debugging,  
LadyBug 🐞
`;
    }

};