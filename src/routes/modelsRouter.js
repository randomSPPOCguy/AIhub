import { Router } from "express";
import { setActiveModel, getActiveModel } from "../services/modelRegistry.js";
import {
  buildModelOverviewPayload,
  buildCloudModelsPayload,
  buildLocalModelsPayload
} from "../services/modelSummary.js";

const router = Router();

router.get("/", (_req, res) => {
  res.json(buildModelOverviewPayload());
});

router.get("/cloud", (_req, res) => {
  res.json(buildCloudModelsPayload());
});

router.get("/local", (_req, res) => {
  res.json(buildLocalModelsPayload({ includeHardware: true }));
});

router.get("/active", (_req, res) => {
  res.json({ activeModel: getActiveModel() });
});

router.post("/select", (req, res) => {
  const { id } = req.body || {};
  if (!id) return res.status(400).json({ error: "id is required" });
  try {
    const model = setActiveModel(id);
    res.json({ object: "model.selected", activeModel: model });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

export default router;
