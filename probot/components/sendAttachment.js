import { replyWithError } from "./sendRatings.js";

/**
 * Sends trace JSON-attachment from an issue body to the flask backend
 *
 * @param {Object} issueBody - Issue body
 * @param {Object} context - The Probot context object.               
 * @returns {Object|null} - Returns the parsed JSON content from attachment link
 */
export const sendAttachment = async (issueBody, context) => {
    const issue = context.payload.issue;
    // Use regex to match a JSON file link in an issue body
    const jsonFileLink = issueBody.match(/https?:\/\/github\.com\/[^\s]+\.json/g);

    // Could optionally send the user a message about using a 
    // GUI augmented bug report for more accurate result here  
    if(!jsonFileLink) {
        console.log(`No JSON attachment found:${jsonFileLink}`);
        return null;
    }

    console.log(`Found JSON attachment: ${jsonFileLink}`);

    try {
        // Get respone and parse JSON content
        const jsonContentResponse = await fetch(jsonFileLink);
        jsonContent = await jsonContentResponse.json();

        console.log(typeof(jsonContent));

        return jsonContent;
    } catch (error) {
        console.error(`Error fetching JSON content: ${error.message}`);
        await replyWithError(context, issue.number, "An error occurred when trying to parse the JSON file. Rankings will be calculated without GUI data.");

        return null;
    }
};
