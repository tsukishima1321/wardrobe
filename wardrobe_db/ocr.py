import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

import torch
import easyocr
import cv2
import numpy as np

torch.set_num_threads(2)

reader: Optional[Any] = None


def load_model() -> None:
    global reader
    if reader is None:
        logger.info("Loading EasyOCR model...")
        reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        logger.info("EasyOCR model loaded.")


def ocrImg(src: str) -> str:
    global reader
    if reader is None:
        load_model()

    logger.info(f"Starting OCR for image: {src}")
    try:
        img: Optional[np.ndarray] = cv2.imread(src)
        if img is None:
            logger.error(f"Failed to read image from {src}")
            return ""

        h, w, _ = img.shape
        croppeds: list[np.ndarray] = []
        max_h = 2000 if w > 1200 else 1000

        for i in range(0, h, max_h):
            croppeds.append(img[i:i + max_h, :])

        res = ""
        for cropped in croppeds:
            result = reader.readtext(cropped, slope_ths=0.5, width_ths=0.7)
            for detection in result:
                res += detection[1].strip()
        logger.info(f"OCR success: {src}")
        return res
    except Exception as e:
        logger.error(f"Error processing image {src}: {e}")
        return ""