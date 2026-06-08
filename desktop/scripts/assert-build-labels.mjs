import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const distDir = join(here, "../dist/assets");
const chunks = readdirSync(distDir)
  .filter((file) => file.endsWith(".js") || file.endsWith(".css"))
  .map((file) => readFileSync(join(distDir, file), "utf8"))
  .join("\n");

const requiredLabels = [
  "Project",
  "Connection",
  "Workflows",
  "Runs",
  "Assets",
  "Settings",
  "Schema",
  "Last reindex",
  "Outputs",
  "Batches",
  "Reindex",
  "Check connection",
  "No workflows indexed",
  "Unable to load",
  "Gallery",
  "Table",
  "Compare",
  "Cleanup",
  "Generate report",
  "Dry run",
  "Confirm cleanup",
  "Favorite",
  "Rating",
  "Notes",
  "Batches",
  "Batch detail",
  "Child runs",
  "Variation parameters",
  "completed",
  "failed"
];

const missing = requiredLabels.filter((label) => !chunks.includes(label));

if (missing.length > 0) {
  console.error(`Missing desktop labels: ${missing.join(", ")}`);
  process.exit(1);
}
