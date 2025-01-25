import { replyWithError } from "./sendRatings.js";
import { traceSchema } from "./traceSchema.js";
import Ajv from "ajv";

/**
 * Validates JSON content against the provided schema and returns error details if invalid.
 *
 * @param {Object} jsonContent - The JSON content to validate
 * @returns {Object} - An object with `isValid` (boolean) and `errors` (array of messages)
 */
const validateJsonSchema = (jsonContent) => {
    const ajv = new Ajv();
    const validate = ajv.compile(traceSchema);
    const isValid = validate(jsonContent);

    if (!isValid) {
        // Map Ajv errors to user-friendly messages
        const errorMessages = validate.errors.map((error) => {
            const field = error.instancePath ? `Field "${error.instancePath.slice(1)}"` : "Root object";
            const message = error.message || "Invalid value.";
            return `${field} ${message}`;
        });

        return {
            isValid: false,
            errors: errorMessages
        };
    }

    return { isValid: true, errors: [] };
};

/**
 * Sends trace JSON-attachment from an issue body to the flask backend
 *
 * @param {Object} issueBody - Issue body
 * @param {Object} context - The Probot context object.
 * @returns {Object|null} - Returns the validated trace JSON content or null if invalid
 */
export const sendTrace = async (issueBody, context) => {
    const issue = context.payload.issue;
    const jsonFileLink = issueBody.match(/https?:\/\/github\.com\/[^\s]+\.json/g);

    if (!jsonFileLink) {
        console.log("No JSON attachment found.");
        return null;
    }

    console.log(`Found JSON attachment: ${jsonFileLink}`);

    // 
    try {
        const jsonContentResponse = await fetch(jsonFileLink);
        const traceContent = await jsonContentResponse.json();

        // Validate JSON content as a valid trace
        const { isValid, errors } = validateJsonSchema(traceContent);

        if (!isValid) {
            console.error("Invalid JSON schema:", errors);

            // Send detailed errors to the issue
            const errorMessage = `The uploaded JSON file has the following issues:\n- ${errors.join("\n- ")}\n\nRankings will be calculated without GUI data.`;
            await replyWithError(context, issue.number, errorMessage);

            return null;
        }

        console.log("Valid JSON schema detected.");
        const traceString = JSON.stringify(traceContent);
        
        // Uncomment to test JSON parse
        // await replyWithTrace(context, issue.number, traceString);

        return traceString;
    } catch (error) {
        console.error(`Error fetching trace JSON contents: ${error.message}`);
        await replyWithError(context, issue.number, "An error occurred while parsing the trace JSON file. Rankings will be calculated without GUI data.");
        return null;
    }
};

/** 
 * TESTING METHOD
 * Replies to the issue with an parsed trace.
 * @param {Object} context - The Probot context object.
 * @param {number} issueNumber - The issue number to reply to.
 * @param {string} traceMessage - The error message to include in the comment.
 */
export const replyWithTrace = async (context, issueNumber, traceMessage) => {
    const commentBody = `Here's the parsed trace string from the issue body (FOR TESING PURPOSES)\n\n ${traceMessage}`;
  
    const issueComment = context.issue({ body: commentBody, issue_number: issueNumber });
  
    try {
      await context.octokit.issues.createComment(issueComment);
      console.log(`Posted trace message to issue #${issueNumber}.`);
    } catch (err) {
      console.error('Failed to post trace message to issue:', err.message);
    }
  };