// Feedback endpoint for TLDR Digest.
// Deploy as: Web app → Execute as "Me" → Access "Anyone".
//
// Handles two actions via GET params:
//   ?action=feedback&vote=up|down&title=...&url=...&source=...&score=...
//   ?action=export  (returns all feedback as JSON for sync_feedback.py)
//
// Setup: create a Google Sheet, paste its ID below, and ensure the first
// sheet is named "Feedback". The script auto-creates the header row.

var SHEET_ID = "REDACTED_SHEET_ID";
var SHEET_NAME = "Feedback Log";

function getOrCreateSheet() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(["Timestamp", "Title", "URL", "Vote", "Source Newsletter", "Claude Score"]);
  }
  return sheet;
}

function doGet(e) {
  var action = (e.parameter.action || "").toLowerCase();

  if (action === "feedback") {
    return handleFeedback(e.parameter);
  }
  if (action === "export") {
    return handleExport();
  }
  if (action === "stats") {
    return handleStats();
  }

  return HtmlService.createHtmlOutput("<p>Unknown action.</p>");
}

function handleFeedback(params) {
  var vote = params.vote || "";
  var title = params.title || "";
  var url = params.url || "";
  var source = params.source || "";
  var score = params.score || "";

  if (!vote || !url) {
    return HtmlService.createHtmlOutput("<p>Missing vote or url.</p>");
  }

  var sheet = getOrCreateSheet();
  sheet.appendRow([
    new Date().toISOString(),
    title,
    url,
    vote,
    source,
    parseInt(score, 10) || 0
  ]);

  var emoji = vote === "up" ? "👍" : "👎";
  var color = vote === "up" ? "#16a34a" : "#dc2626";
  var bg = vote === "up" ? "#f0fdf4" : "#fef2f2";
  var label = vote === "up" ? "More like this" : "Less like this";

  var html = '<!DOCTYPE html><html><head><meta charset="utf-8">'
    + '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
    + '<title>Feedback recorded</title></head>'
    + '<body style="margin:0;padding:40px 20px;background:#f4f4f5;'
    + 'font-family:-apple-system,BlinkMacSystemFont,sans-serif;text-align:center;">'
    + '<div style="max-width:400px;margin:0 auto;background:#fff;border-radius:12px;'
    + 'padding:32px 24px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">'
    + '<div style="font-size:48px;margin-bottom:12px;">' + emoji + '</div>'
    + '<div style="display:inline-block;padding:4px 12px;border-radius:14px;'
    + 'font-size:14px;font-weight:600;background:' + bg + ';color:' + color + ';">'
    + label + '</div>'
    + '<p style="margin:16px 0 4px;font-size:15px;font-weight:600;color:#18181b;">'
    + title + '</p>'
    + '<p style="font-size:13px;color:#71717a;margin:0;">Noted! This will shape future digests.</p>'
    + '</div></body></html>';

  return HtmlService.createHtmlOutput(html)
    .setTitle("Feedback recorded");
}

function handleExport() {
  var sheet = getOrCreateSheet();
  var data = sheet.getDataRange().getValues();
  if (data.length <= 1) {
    return ContentService.createTextOutput(JSON.stringify([]))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var headers = data[0];
  var rows = [];
  for (var i = 1; i < data.length; i++) {
    var row = {};
    for (var j = 0; j < headers.length; j++) {
      row[headers[j]] = data[i][j];
    }
    rows.push(row);
  }

  return ContentService.createTextOutput(JSON.stringify(rows))
    .setMimeType(ContentService.MimeType.JSON);
}

function handleStats() {
  var sheet = getOrCreateSheet();
  var data = sheet.getDataRange().getValues();

  var ups = 0;
  var downs = 0;
  var recent = [];

  for (var i = data.length - 1; i >= 1; i--) {
    var vote = data[i][3];
    if (vote === "up") ups++;
    if (vote === "down") downs++;
    if (recent.length < 10) {
      recent.push({
        title: data[i][1],
        vote: vote,
        date: data[i][0]
      });
    }
  }

  var recentHtml = "";
  for (var k = 0; k < recent.length; k++) {
    var emoji = recent[k].vote === "up" ? "👍" : "👎";
    recentHtml += '<div style="padding:8px 0;border-bottom:1px solid #f0f0f0;'
      + 'font-size:13px;color:#52525b;">'
      + emoji + " " + recent[k].title + '</div>';
  }

  var html = '<!DOCTYPE html><html><head><meta charset="utf-8">'
    + '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
    + '<title>Feedback Stats</title></head>'
    + '<body style="margin:0;padding:40px 20px;background:#f4f4f5;'
    + 'font-family:-apple-system,BlinkMacSystemFont,sans-serif;">'
    + '<div style="max-width:400px;margin:0 auto;background:#fff;border-radius:12px;'
    + 'padding:24px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">'
    + '<h2 style="margin:0 0 16px;font-size:18px;color:#18181b;">'
    + '📊 Feedback Stats</h2>'
    + '<div style="display:flex;gap:16px;margin-bottom:20px;">'
    + '<div style="flex:1;text-align:center;padding:12px;background:#f0fdf4;border-radius:8px;">'
    + '<div style="font-size:24px;font-weight:700;color:#16a34a;">' + ups + '</div>'
    + '<div style="font-size:12px;color:#71717a;">👍 upvotes</div></div>'
    + '<div style="flex:1;text-align:center;padding:12px;background:#fef2f2;border-radius:8px;">'
    + '<div style="font-size:24px;font-weight:700;color:#dc2626;">' + downs + '</div>'
    + '<div style="font-size:12px;color:#71717a;">👎 downvotes</div></div></div>'
    + '<h3 style="margin:0 0 8px;font-size:14px;color:#71717a;">Recent</h3>'
    + recentHtml
    + '</div></body></html>';

  return HtmlService.createHtmlOutput(html).setTitle("Feedback Stats");
}
