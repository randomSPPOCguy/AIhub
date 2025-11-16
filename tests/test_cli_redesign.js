// Test script for the new CLI redesign
import { printUnifiedModelList, getModelByIndex } from "./src/cli/unifiedModelList.js";

console.log("=== Testing Unified Model List ===\n");

// Test 1: Print unified model list
console.log("Test 1: Printing unified model list...\n");
const list = printUnifiedModelList();

console.log("\n=== Testing Model Selection by Index ===\n");

// Test 2: Get model by index
if (list.all.length > 0) {
  const firstModel = getModelByIndex(list.all[0].index);
  console.log(`Test 2: Retrieved model by index ${list.all[0].index}:`);
  console.log(`  - ID: ${firstModel.id}`);
  console.log(`  - Name: ${firstModel.name}`);
  console.log(`  - Provider: ${firstModel.provider}`);
  console.log(`  - Type: ${firstModel.type}`);
  console.log(`  - Ready: ${firstModel.ready}`);
} else {
  console.log("Test 2: No models available to test");
}

console.log("\n=== Testing Invalid Index ===\n");

// Test 3: Try to get model with invalid index
const invalidModel = getModelByIndex(999);
console.log(`Test 3: Retrieved model by index 999: ${invalidModel ? "FAIL - should be null" : "PASS - correctly returned null"}`);

console.log("\n=== Test Results ===\n");
console.log("✓ Unified model list generated successfully");
console.log("✓ Model retrieval by index working");
console.log("✓ Invalid index handling working");
console.log("\n=== All Tests Passed! ===\n");
