import { Router } from "express";
import { z } from "zod";
import { onSongEnded } from "../harvest/afterPlay.js";

const router = Router();

const PlaySchema = z.object({
  roomId: z.string().min(1),
  username: z.string().min(1),
  userId: z.string().min(1),
  artist: z.string().min(1),
  title: z.string().min(1),
  album: z.string().optional().nullable(),
  year: z.number().int().optional().nullable(),
  genre: z.string().optional().nullable(),
  provider: z.string().optional().nullable(),
  eventId: z.string().min(1)
});

router.post("/song-ended", async (req, res) => {
  try {
    const body = PlaySchema.parse(req.body);
    const out = await onSongEnded(body);
    res.json({ ok: true, ...out });
  } catch (e) {
    res.status(400).json({ ok: false, error: e.message });
  }
});

export default router;
