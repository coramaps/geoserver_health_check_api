from datetime import date
import datetime
from logging import config
from turtle import st
from fastapi import FastAPI
import logging
from api import CONFIG
from geoserver_check_s2_rgb.test_wms import test_least_cloudiest_rgb_image_for_region_and_timespan


WMS_URL=CONFIG.get("GEOSERVER", "wms_url")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/ping")
async def ping():
    logger.info("Received ping request")
    return {"message": "pong"}


@app.get("/test_random_aws_images_on_geoserver")
async def test_random_aws_images_on_geoserver(start:str=None, end:str=None, duration_days:int=30,
                                              rgblayer:str="coramaps:s2_rgb",
                                              bounds:list[float,float,float,float]=(0.748182,44.6840129,0.7618833,44.69329)):
    
    start, end=[date.fromisoformat(x) if isinstance(x, str) else x for x in (start, end)]
    
    if end is None:
        end = date.today()-datetime.timedelta(days=2)
    if start is None:
        start = end - datetime.timedelta(days=duration_days)
    logger.info(f"Testing random AWS images from {start} to {end}")
  
    
    
    
    corr, p, num_pixels =test_least_cloudiest_rgb_image_for_region_and_timespan(wgs84_bounds=bounds,
        timespan=[start, end],
        wms_url=WMS_URL,
        layer=rgblayer
        )
    try:
        assert corr > 0.9, f"Correlation is too low: {corr}"
        assert p < 0.05, f"P-value is too high: {p}"
        assert num_pixels > 100, f"Number of valid pixels is too low: {num_pixels}"
    except AssertionError as e:
        logger.error(f"Test failed: {e}")
        return {"error": str(e)}
    logger.info(f"Test passed: Correlation={corr}, P-value={p}, Number of valid pixels={num_pixels}")
    return {
        "correlation": corr,
        "p_value": p,
        "num_valid_pixels": num_pixels
    }
    