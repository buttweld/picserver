import sys
import os
import logging
import time
from PIL import Image
from app.vendor.waveshare_epd import epd7in3f

logging.basicConfig(level=logging.INFO)

def update_epd7in3f_display(bmp_path: str):
    """
    Displays the given BMP image on the Waveshare 7.3-inch color e-paper display.
    """
    try:
        logging.info("Displaying image on Waveshare 7.3f e-paper")

        epd = epd7in3f.EPD()
        epd.init()

        Himage = Image.open(bmp_path)
        epd.display(epd.getbuffer(Himage))
        time.sleep(1)

        logging.info("Display update complete. Going to sleep.")
        epd.sleep()

    except Exception as e:
        logging.exception(f"Error displaying image: {e}")
        try:
            epd7in3f.epdconfig.module_exit(cleanup=True)
        except Exception:
            pass
