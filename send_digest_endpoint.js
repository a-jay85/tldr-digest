// Add this to your existing tldr-feedback-endpoint.js in Google Apps Script,
// then redeploy the web app (New Deployment → Web App).
//
// This adds a doPost handler that sends the digest email via GmailApp.
// The routine POSTs JSON: { action: "sendDigest", subject: "...", htmlBody: "..." }

function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);

    if (payload.action === "sendDigest") {
      return sendDigestEmail(payload);
    }

    return ContentService
      .createTextOutput(JSON.stringify({ status: "error", message: "Unknown action" }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function sendDigestEmail(payload) {
  var recipient = PropertiesService.getScriptProperties().getProperty("EMAIL");
  var subject = payload.subject || "TLDR Digest";
  var htmlBody = payload.htmlBody || "<p>No content</p>";

  GmailApp.sendEmail(recipient, subject, "", { htmlBody: htmlBody });

  return ContentService
    .createTextOutput(JSON.stringify({ status: "ok", message: "Digest sent to " + recipient }))
    .setMimeType(ContentService.MimeType.JSON);
}
