export const sendAttachment = async (issueBody) => {
    // Use regex to match a JSON file link in an issue body
    const jsonFileLinks = issueBody.match('https?:\/\/github\.com\/[^\s]+\.json')

    if(!jsonFileLinks) {
        console.log("No JSON attachments found.");
        return;
    }

    console.log(`Found JSON attachment: ${jsonFileLinks}`)
    console.log(issueBody);
};

 