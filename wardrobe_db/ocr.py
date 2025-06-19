import logging

logger = logging.getLogger(__name__)

import torch
import easyocr
import cv2

torch.set_num_threads(2)

reader = easyocr.Reader(['ch_sim','en'],gpu=False)

def ocrImg(src:str) -> str:
    logger.info(f"Starting OCR for image: {src}")
    try:
        img = cv2.imread(src)
        if img is None:
            logger.error(f"Failed to read image from {src}")
            return ""
        
        h, w, _ = img.shape
        croppeds = []
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