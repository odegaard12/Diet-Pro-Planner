"""Image handling limits: no huge upscales for the OCR, and uploads are validated before they touch the disk."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

import _env  # noqa: F401  (isolated data dir + auth token; must come first)
from PIL import Image

import dpp_entrypoint

legacy = dpp_entrypoint.legacy


class ImageLimitTests(unittest.TestCase):
    def test_narrow_image_is_not_upscaled_to_a_huge_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "narrow.png"
            Image.new("L", (1, 30000), 128).save(path)  # would be 1200 x 36,000,000 without the guard
            out = legacy._ocr3_preprocess_fast(path)
            self.assertLessEqual(out.size[0] * out.size[1], 16_000_000)

    def test_small_image_is_still_upscaled_for_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "small.png"
            Image.new("L", (600, 400), 200).save(path)
            self.assertEqual(legacy._ocr3_preprocess_fast(path).size, (1200, 800))

    def test_fake_image_is_rejected_and_not_stored(self) -> None:
        client = legacy.app.test_client()
        before = set(legacy.UPLOADS.glob("*"))
        r = client.post("/api/food-photo", headers=_env.AUTH, data={"photo": (io.BytesIO(b"<?php echo 1; ?>"), "x.png")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(legacy.UPLOADS.glob("*")), before)

    def test_real_image_is_stored(self) -> None:
        client = legacy.app.test_client()
        buf = io.BytesIO()
        Image.new("RGB", (40, 40), "red").save(buf, format="PNG")
        buf.seek(0)
        r = client.post("/api/food-photo", headers=_env.AUTH, data={"photo": (buf, "ok.png")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        self.assertTrue((legacy.UPLOADS / r.get_json()["photo_path"].rsplit("/", 1)[1]).exists())


if __name__ == "__main__":
    unittest.main()
