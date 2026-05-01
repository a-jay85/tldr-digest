// Auto-send digest drafts via a time-based trigger.
// Add this to the same Apps Script project as your feedback endpoint.
//
// Run installDigestTrigger() once from the editor to set up the daily trigger.
// It will run sendPendingDigest() every day at ~11:30 AM Pacific.

var SUBJECT_MATCH = "TLDR Digest";
var MAX_DRAFT_AGE_HOURS = 18;

function sendPendingDigest() {
  var drafts = GmailApp.getDrafts();
  var now = new Date();
  var sent = 0;

  for (var i = 0; i < drafts.length; i++) {
    var msg = drafts[i].getMessage();
    var subject = msg.getSubject();

    if (subject.indexOf(SUBJECT_MATCH) === -1) continue;

    var ageMs = now.getTime() - msg.getDate().getTime();
    var ageHours = ageMs / (1000 * 60 * 60);
    if (ageHours > MAX_DRAFT_AGE_HOURS) continue;

    drafts[i].send();
    sent++;
    Logger.log("Sent draft: " + subject);
  }

  Logger.log("sendPendingDigest complete. Sent " + sent + " draft(s).");
}

function installDigestTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === "sendPendingDigest") {
      Logger.log("Trigger already exists — deleting old one first.");
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }

  ScriptApp.newTrigger("sendPendingDigest")
    .timeBased()
    .everyDays(1)
    .atHour(11)
    .nearMinute(30)
    .create();

  Logger.log("Installed daily trigger for sendPendingDigest at ~11:30 AM project time.");
}
