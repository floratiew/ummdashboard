const express = require("express");
const fs = require("fs");
const path = require("path");
const { parse } = require("csv-parse/sync");

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_DIR = path.join(__dirname, "data");
const PUBLIC_DIR = path.join(__dirname, "public");
const WATER_VALUES_FILE = path.join(DATA_DIR, "water_values_no2.json");
const UMM_MESSAGES_FILE = path.join(DATA_DIR, "umm_messages.csv");

const MESSAGE_TYPE_LABELS = {
  1: "Production unavailability",
  2: "Consumption unavailability",
  3: "Transmission outage",
  4: "Market notice",
  5: "Other market information",
};

const EVENT_STATUS_LABELS = {
  1: "Active",
  3: "Cancelled / postponed",
};

let waterCache = null;
function loadWaterValues() {
  if (waterCache) return waterCache;
  const raw = fs.readFileSync(WATER_VALUES_FILE, "utf-8");
  waterCache = JSON.parse(raw);
  return waterCache;
}

function safeJsonParseArray(value) {
  if (!value || typeof value !== "string") return [];
  const trimmed = value.trim();
  if (!trimmed) return [];
  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) return parsed;
    if (parsed && typeof parsed === "object") return [parsed];
  } catch (err) {
    return [];
  }
  return [];
}

function extractArea(record) {
  const areas = [];
  const appendArea = (value) => {
    if (!value) return;
    const trimmed = String(value).trim();
    if (trimmed) areas.push(trimmed.toUpperCase());
  };

  for (const item of safeJsonParseArray(record.areas_json)) {
    appendArea(item?.name);
  }
  for (const item of safeJsonParseArray(record.production_units_json)) {
    appendArea(item?.areaName);
  }
  for (const item of safeJsonParseArray(record.generation_units_json)) {
    appendArea(item?.areaName);
  }

  const code = areas.find((value) => /^[A-Z]{2}\d$/.test(value) || /^NO\d$/i.test(value));
  if (code) return code;
  return areas[0] || "UNKNOWN";
}

function extractResource(record) {
  const production = safeJsonParseArray(record.production_units_json);
  if (production.length) {
    const first = production[0];
    return first?.productionUnitName || first?.name || "Unknown unit";
  }
  const generation = safeJsonParseArray(record.generation_units_json);
  if (generation.length) {
    const first = generation[0];
    return first?.name || "Unknown unit";
  }
  return "Unspecified resource";
}

function extractCapacityMw(record) {
  let total = 0;
  for (const unit of safeJsonParseArray(record.production_units_json)) {
    const periods = Array.isArray(unit?.timePeriods) ? unit.timePeriods : [];
    for (const period of periods) {
      if (period?.unavailableCapacity != null) {
        total += Number(period.unavailableCapacity) || 0;
      }
    }
  }
  return Number(total.toFixed(1));
}

function mapEventStatus(value) {
  const numeric = Number(value);
  return EVENT_STATUS_LABELS[numeric] || "Other";
}

function mapMessageType(value) {
  const numeric = Number(value);
  return MESSAGE_TYPE_LABELS[numeric] || "Other";
}

function hydrateUmmRecord(raw) {
  return {
    messageId: raw.message_id,
    publicationTime: raw.publication_date,
    eventStart: raw.event_start,
    eventEnd: raw.event_stop,
    participant: raw.publisher_name || "Unknown",
    powerSystemResource: extractResource(raw),
    area: extractArea(raw),
    outageType: mapMessageType(raw.message_type),
    status: mapEventStatus(raw.event_status),
    capacityAffectedMw: extractCapacityMw(raw),
    message: raw.remarks || raw.unavailability_reason || "",
    lastUpdate: raw.retrieved_at,
  };
}

let ummCache = null;
function loadUmmMessages() {
  if (ummCache) return ummCache;
  const raw = fs.readFileSync(UMM_MESSAGES_FILE, "utf-8");
  const records = parse(raw, {
    columns: true,
    skip_empty_lines: true,
    relax_quotes: true,
  });
  ummCache = records.map(hydrateUmmRecord);
  return ummCache;
}

function buildUmmSummary(records) {
  const totalsByArea = new Map();
  const capacityByArea = new Map();
  const statusCounts = new Map();
  const typeCounts = new Map();
  const largeEvents = new Map();

  let capacitySum = 0;
  let activeCount = 0;

  for (const item of records) {
    const area = item.area || "UNKNOWN";
    const cap = Number(item.capacityAffectedMw || 0);
    const status = item.status || "Unknown";
    const type = item.outageType || "Other";

    totalsByArea.set(area, (totalsByArea.get(area) || 0) + 1);
    capacityByArea.set(area, (capacityByArea.get(area) || 0) + cap);
    statusCounts.set(status, (statusCounts.get(status) || 0) + 1);
    typeCounts.set(type, (typeCounts.get(type) || 0) + 1);

    capacitySum += cap;
    if (status === "Active") activeCount += 1;

    if (cap >= 50) {
      const current = largeEvents.get(area) || { area, events: 0, maxCapacityMw: 0 };
      current.events += 1;
      if (cap > current.maxCapacityMw) current.maxCapacityMw = cap;
      largeEvents.set(area, current);
    }
  }

  const areaTotals = Array.from(totalsByArea.entries())
    .map(([area, issues]) => ({
      area,
      issues,
      capacityMw: Number((capacityByArea.get(area) || 0).toFixed(1)),
    }))
    .sort((a, b) => b.issues - a.issues);

  const statusBreakdown = Array.from(statusCounts.entries())
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => b.count - a.count);

  const outageTypeBreakdown = Array.from(typeCounts.entries())
    .map(([outageType, count]) => ({ outageType, count }))
    .sort((a, b) => b.count - a.count);

  const largeOutages = Array.from(largeEvents.values()).sort(
    (a, b) => b.maxCapacityMw - a.maxCapacityMw,
  );

  return {
    overview: {
      totalMessages: records.length,
      activeMessages: activeCount,
      totalCapacityAffectedMw: Number(capacitySum.toFixed(1)),
      statusBreakdown,
      outageTypeBreakdown,
    },
    areaTotals,
    largeOutages,
  };
}

app.get("/api/water-values", (_req, res) => {
  try {
    const payload = loadWaterValues();
    res.json(payload);
  } catch (error) {
    console.error("Failed to load water values data:", error);
    res.status(500).json({ error: "Failed to load water value dataset" });
  }
});

app.get("/api/umms", (_req, res) => {
  try {
    const payload = loadUmmMessages();
    res.json(payload);
  } catch (error) {
    console.error("Failed to load UMM dataset:", error);
    res.status(500).json({ error: "Failed to load UMM dataset" });
  }
});

app.get("/api/umm/summary", (_req, res) => {
  try {
    const messages = loadUmmMessages();
    const summary = buildUmmSummary(messages);

    res.json({
      generatedAt: new Date().toISOString(),
      ...summary,
    });
  } catch (error) {
    console.error("Failed to load UMM summary data:", error);
    res.status(500).json({ error: "Failed to load UMM summary data" });
  }
});

app.get("/health", (_req, res) => {
  res.json({ ok: true, timestamp: new Date().toISOString() });
});

app.use(express.static(PUBLIC_DIR));

app.get("*", (_req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, "index.html"));
});

app.listen(PORT, () => {
  console.log(`Prototype server listening on http://localhost:${PORT}`);
});
