/**
 * CreatorPulse — Phase 5 Apps Script layer.
 *
 * Synced to the Sheet by pasting this file whole into Extensions > Apps Script > Code.gs —
 * never hand-edited in the browser (D-04). Bound to the "Dashboard" tab; column G, STATUS_COLUMN
 * below, is the one cell range a human owns and this file only ever reads, never writes.
 */

const DASHBOARD_TAB = 'Dashboard'; // Phase 4 D-03 — the frozen tab name, never re-derived
const STATUS_COLUMN = 7; // column G, frozen by Phase 4 D-03
const CREATOR_COLUMN = 1; // column A — the name D-14's message uses
const SOURCE_COLUMN = 2; // column B — the other name D-14's message uses
const FIRST_DATA_ROW = 2; // row 1 is the header; an edit to row 1 of G is not a Status edit
const WEBHOOK_PROPERTY = 'DISCORD_WEBHOOK_URL'; // D-13 — read at call time, never hardcoded

const LAST_UPDATED_COLUMN = 6; // column F, "Last updated (UTC)"
// D-06: the collector runs 08:00 Manila = 00:00 UTC (Phase 2 D-09), so 09:00 is one hour
// after the run should have finished, and 26 hours alerts on a genuinely missed run while
// tolerating one that was merely slow, retried, or a little late.
const STALE_THRESHOLD_HOURS = 26;
const WATCHDOG_HOUR = 9;
const SCRIPT_TIMEZONE = 'Asia/Manila';

// 05-02 appends DELTA_RANGE, POSITIVE_BACKGROUND, NEGATIVE_BACKGROUND beside these.

/**
 * Simple trigger — builds the menu. Needs no authorization, so it runs for anyone who opens
 * the Sheet, whether or not anybody has installed anything yet. Reads no Sheet data: an
 * empty, header-only, or entirely absent Dashboard tab cannot suppress this menu.
 */
function onOpen(e) {
  SpreadsheetApp.getUi()
    .createMenu('CreatorPulse')
    .addItem('Check freshness now', 'checkFreshness')
    .addItem('Install triggers', 'installTriggers')
    .addToUi();
  // Task 2 inserts 'Re-apply formatting' between the two items above, in D-09's stated order.
}

/**
 * The duplicate-guard D-09 pays for. Deletes every trigger this script project owns before
 * creating any — the enumeration below returns only this project's triggers, so the delete
 * pass cannot touch anything else. Without it, clicking this item twice would create two
 * onEdit triggers and one Status edit would post to Discord twice.
 */
function installTriggers() {
  const ss = SpreadsheetApp.getActive();

  let removedCount = 0;
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    ScriptApp.deleteTrigger(trigger);
    removedCount++;
  });

  ScriptApp.newTrigger('onStatusEdit').forSpreadsheet(ss).onEdit().create();

  // The watchdog's daily fire (D-05, D-06). .inTimezone() is not redundant with the
  // manifest's timeZone even though both say Asia/Manila — this call is what actually pins
  // atHour() to Manila local time; the manifest is only the fallback when this is omitted.
  ScriptApp.newTrigger('checkFreshness')
    .timeBased()
    .atHour(WATCHDOG_HOUR)
    .everyDays(1)
    .inTimezone(SCRIPT_TIMEZONE)
    .create();
  const createdCount = 2;

  ss.toast(
    'Removed ' + removedCount + ' trigger(s), created ' + createdCount + '.',
    'CreatorPulse'
  );
}

/**
 * The installable onEdit target (SCRIPT-03). Deliberately NOT named after the simple-trigger
 * event name — that name cannot reach UrlFetchApp and the failure is silent from the editing
 * user's point of view. Only ever created through installTriggers() above.
 */
function onStatusEdit(e) {
  const range = e.range;
  const sheet = range.getSheet();

  // A gspread/API write never fires an edit event at all — only a human edit through the
  // Sheets UI does — so the daily sync can never reach this handler.
  if (
    sheet.getName() !== DASHBOARD_TAB ||
    range.getColumn() !== STATUS_COLUMN ||
    range.getRow() < FIRST_DATA_ROW
  ) {
    return;
  }

  const row = range.getRow();
  const creator = sheet.getRange(row, CREATOR_COLUMN).getValue();
  const source = sheet.getRange(row, SOURCE_COLUMN).getValue();

  // D-15: a missing old value is rendered, never assumed — undefined for any multi-cell edit.
  const oldValue = e.oldValue !== undefined ? e.oldValue : '(blank)';

  // e.value is undefined both when the cell was cleared AND when the edit spanned multiple
  // cells. Reading the cell back distinguishes the two, so a multi-cell paste never reports a
  // clear that did not happen. Residual limit: a multi-cell edit reports only its top-left row.
  let newValue;
  if (e.value !== undefined) {
    newValue = e.value;
  } else {
    const currentValue = range.getValue();
    newValue = currentValue === '' || currentValue === null ? '(cleared)' : currentValue;
  }

  postToDiscord(creator + ' / ' + source + ' — Status: ' + oldValue + ' → ' + newValue);
}

/**
 * D-13 — the webhook URL lives in Script Properties, never in this file. Falsy check rather
 * than `=== null` since getProperty()'s return for an unset key is only assumed, not confirmed;
 * a falsy check catches null, undefined, and empty string identically.
 */
function getWebhookUrl() {
  const url = PropertiesService.getScriptProperties().getProperty(WEBHOOK_PROPERTY);
  if (!url) {
    throw new Error(
      'Script Property ' +
        WEBHOOK_PROPERTY +
        ' is not set. Project Settings (gear icon) > Script Properties > add ' +
        WEBHOOK_PROPERTY +
        ' with the Discord webhook URL, then Save script properties.'
    );
  }
  return url;
}

/**
 * The shared poster — called by this plan's handler and by 05-02's watchdog. JSON.stringify
 * escapes free-text Status content by construction, so a quote or backslash typed into a
 * Status cell cannot break the request body. The empty mention-parse list below suppresses
 * @everyone/@here/role pings, since the Sheet is link-editable (T-05-05).
 */
function postToDiscord(message) {
  const webhookUrl = getWebhookUrl();
  const response = UrlFetchApp.fetch(webhookUrl, {
    method: 'post',
    contentType: 'application/json',
    muteHttpExceptions: true,
    payload: JSON.stringify({
      content: message,
      allowed_mentions: { parse: [] },
    }),
  });

  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    // Log the response code and body only — never the webhook URL and never a raw thrown
    // error that could carry it (T-05-02). No retry loop: this is one POST a handful of
    // times a day, not a batch job.
    console.error('Discord webhook returned ' + code + ': ' + response.getContentText());
  }
}

/**
 * The stale-data watchdog (D-05, D-06, D-07, SCRIPT-02). Called by the daily time-driven
 * trigger and by the "Check freshness now" menu item — same function, no duplicated logic.
 *
 * Exactly three outcomes:
 *   1. Cannot determine — missing tab, header-only tab, or nothing in column F parses. Posts
 *      a DISTINCT alert. D-07 makes silence mean exactly one thing ("the data is fresh"), so
 *      a parse failure must never be reported as staleness and must never stay silent — a
 *      silent return here would reproduce PITFALLS.md §18(d) inside the thing built to answer
 *      it, and would look identical to a healthy day.
 *   2. Stale — newest parseable timestamp is more than STALE_THRESHOLD_HOURS old. Posts an
 *      alert naming that timestamp and the age.
 *   3. Fresh — returns, posting nothing.
 */
function checkFreshness() {
  const sheet = SpreadsheetApp.getActive().getSheetByName(DASHBOARD_TAB);
  if (!sheet) {
    postToDiscord('Watchdog: could not determine freshness — the "' + DASHBOARD_TAB + '" tab is missing.');
    return;
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < FIRST_DATA_ROW) {
    postToDiscord('Watchdog: could not determine freshness — the "' + DASHBOARD_TAB + '" tab has no data rows.');
    return;
  }

  // One batched range read, not a per-row getValue() — same batching judgment SHEET-05
  // applies on the Python side.
  const values = sheet
    .getRange(FIRST_DATA_ROW, LAST_UPDATED_COLUMN, lastRow - FIRST_DATA_ROW + 1, 1)
    .getValues();

  let newestMs = null;
  values.forEach(function (row) {
    const raw = row[0];
    if (raw === '' || raw === null || raw === undefined) {
      return; // an empty column F cell is an absent row, not a parse failure
    }
    // Wave 0 answer (05-01): column F lands as a string under USER_ENTERED, not a Date.
    // Keep both branches anyway — a future value_input_option change cannot silently break
    // this — and discard a NaN candidate at parse time, before it can win the comparison.
    // An unguarded NaN would make the staleness comparison below false forever: the watchdog
    // would stay permanently and silently quiet, which is the failure direction that looks
    // exactly like health.
    const asDate = raw instanceof Date ? raw : new Date(raw);
    const ms = asDate.getTime();
    if (isNaN(ms)) {
      return;
    }
    if (newestMs === null || ms > newestMs) {
      newestMs = ms;
    }
  });

  if (newestMs === null) {
    postToDiscord(
      'Watchdog: could not determine freshness — no cell in column F of "' +
        DASHBOARD_TAB +
        '" parsed to a real date.'
    );
    return;
  }

  // Epoch milliseconds on both sides — a duration, no timezone conversion belongs here.
  const ageHours = (Date.now() - newestMs) / 3600000;
  // Strict '>': an age of exactly 26.0 hours stays silent. That is the tolerant direction,
  // right for a threshold chosen to absorb a slow run rather than to catch one.
  if (ageHours > STALE_THRESHOLD_HOURS) {
    postToDiscord(
      'Watchdog: the collector has not run since ' +
        new Date(newestMs).toISOString() +
        ' (' +
        Math.round(ageHours) +
        'h ago).'
    );
  }
  // Fresh: return without posting anything. Silence means fresh and nothing else.
}

/**
 * RESEARCH.md Pitfall 4 — the phase's one genuine empirical unknown. Python writes column F
 * as an ISO-8601 string with a +00:00 offset; whether that lands in Sheets as text or as a
 * real Date under USER_ENTERED decides how 05-02's staleness arithmetic must read it. Getting
 * it wrong fails in the dangerous direction: a NaN comparison is always false, so the watchdog
 * would stay permanently and silently quiet. Run once from the editor's Run dropdown; no menu
 * item calls this. Underscore-prefixed so its diagnostic status is visible at a glance.
 */
function _diagnoseTimestampType() {
  const sheet = SpreadsheetApp.getActive().getSheetByName(DASHBOARD_TAB);
  const raw = sheet.getRange(2, 6).getValue(); // F2 — the frozen "Last updated (UTC)" column

  Logger.log('typeof: ' + typeof raw);
  Logger.log('instanceof Date: ' + (raw instanceof Date));
  Logger.log('raw value: ' + raw);
  Logger.log('new Date(raw) is NaN: ' + isNaN(new Date(raw).getTime()));
}
