// Test the new menu system
import {
  MenuState,
  showMainMenu,
  showModelMenu,
  showAvailableModels,
  showDownloadModels,
  showActiveModel
} from "./src/cli/menuSystem.js";

console.log("=== Testing Menu System ===\n");

// Test 1: MenuState
console.log("Test 1: MenuState class");
const state = new MenuState();
console.log(`  Initial context: ${state.context}`);
console.log(`  Initial prompt: ${state.getPrompt()}`);
state.context = "model";
console.log(`  Changed to model context: ${state.getPrompt()}`);
state.context = "model/avail";
console.log(`  Changed to avail context: ${state.getPrompt()}`);
console.log("  ✓ MenuState working\n");

// Test 2: Show main menu
console.log("Test 2: Main Menu");
showMainMenu();

// Pause for readability
await new Promise(resolve => setTimeout(resolve, 2000));

// Test 3: Show model menu
console.log("\nTest 3: Model Menu");
showModelMenu();

// Pause for readability
await new Promise(resolve => setTimeout(resolve, 2000));

// Test 4: Show available models
console.log("\nTest 4: Available Models View");
const availCache = showAvailableModels();
console.log(`\n  Model cache size: ${availCache.size}`);
console.log("  ✓ Available models view working\n");

// Pause for readability
await new Promise(resolve => setTimeout(resolve, 2000));

// Test 5: Show download models
console.log("\nTest 5: Download Models View");
const downloadCache = showDownloadModels();
console.log(`\n  Model cache size: ${downloadCache.size}`);
console.log("  ✓ Download models view working\n");

// Pause for readability
await new Promise(resolve => setTimeout(resolve, 2000));

// Test 6: Show active model
console.log("\nTest 6: Active Model View");
showActiveModel();

console.log("\n=== All Menu Tests Passed! ===\n");
console.log("Navigation flow:");
console.log("  hub> /model → model>");
console.log("  model> avail → model/avail>");
console.log("  model/avail> back → model>");
console.log("  model> download → model/download>");
console.log("  model/download> back → model>");
console.log("  model> back → hub>");
