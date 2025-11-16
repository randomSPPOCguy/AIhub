// Test model selection
import { listCloudModels, getModelById, setActiveModel, getActiveModel } from "./src/services/modelRegistry.js";

console.log("=== Testing Cloud Model Registration ===\n");

// Test 1: List cloud models
const cloudModels = listCloudModels();
console.log(`Test 1: Found ${cloudModels.length} cloud models`);
cloudModels.forEach(model => {
  console.log(`  - ${model.id}: ${model.name}`);
});

// Test 2: Get model by ID
console.log("\nTest 2: Get model by ID");
const testModel = getModelById("openai:gpt-4o-mini");
if (testModel) {
  console.log(`  ✓ Found: ${testModel.id} (${testModel.provider})`);
} else {
  console.log(`  ✗ Not found: openai:gpt-4o-mini`);
}

// Test 3: Set active model
console.log("\nTest 3: Set active model to openai:gpt-4o-mini");
try {
  const updated = setActiveModel("openai:gpt-4o-mini");
  console.log(`  ✓ Active model set to: ${updated.id}`);

  // Verify
  const active = getActiveModel();
  console.log(`  ✓ Verified active model: ${active.id}`);
} catch (err) {
  console.log(`  ✗ Error: ${err.message}`);
}

console.log("\n=== All Tests Complete ===");
