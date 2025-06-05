import io
import os
# import sys

import numpy as np
from scipy.stats import pearsonr

# sys.path.append(os.getcwd())
from affine import Affine

from geoserver_check_s2_rgb.get_latest_stac_images import stacSearch   
import requests
import rasterio as rio
from rasterio.io import MemoryFile
from PIL import Image
import geopandas as gpd
import shapely
import json
from datetime import date,datetime
from types import SimpleNamespace


def fetch_wms_image(bbox,start,  wms_url, layer, end=None,dst_crs="EPSG:4326",
                    res=10
                    ):
    # ts="2022-01-01T09:33:35.440Z/2025-02-11T10:49:48.818Z"
    if end is None:
        end=start
    ts=f"{start.isoformat()}T00:00:00.001Z/{end}T23:59:59.999Z"
    bboxstr=",".join([str(x) for x in bbox])
    width=int((bbox[2]-bbox[0])/res)
    height=int((bbox[3]-bbox[1])/res)
    url = (
        wms_url
        + "request=GetMap&"
        + f"layers={layer}&"
        + "bbox="+bboxstr+"&"
        + f"width={width}&height={height}&"
        + f"crs={dst_crs}&"
        + "format=image/png&"
        + "transparent=true&"
        + "version=1.3.0&"
        + "format_options=dpi:144&"
        + "dpi=144&"
        # +"DIM_CLOUD_COVER=0/100&"
        # + "timeDimensionExtent="+ts
        + "TIME="+ts
    )
    # print("geoserver url: \n"+url)
    # Make a GET request to the WMS server
    response = requests.get(url)
    
    
    # Check that the HTTP response status is 200
    assert response.status_code == 200, f"Expected status code 200 but received {response.status_code}"
    response.url
    # Check that the Content-Type header indicates an image
    content_type = response.headers.get("Content-Type", "")
    assert content_type.startswith("image/"), f"Expected image Content-Type but got {content_type}"
    response.text
    # Verify that the image content is valid by opening it with PIL
    try:
        with io.BytesIO(response.content) as image_io:
            image = Image.open(image_io)
            image.verify()
    except Exception as e:
        raise AssertionError(f"Image verification failed: {e}")
    with MemoryFile(response.content) as memfile, memfile.open() as op:
        d=op.read()
        prf=op.profile
        # Initialize the profile based on df_img.unary_union.bounds, res_in_m, and imgcrs
        prf.update({
            "driver": "GTiff",
            # "height": int((bb[3] - bb[1]) / res_in_m),
            # "width": int((bb[2] - bb[0]) / res_in_m),
            "transform": rio.transform.from_bounds(*bbox, 
                                                    prf["width"], 
                                                    prf["height"]),
            "crs": dst_crs
        })
        
    return d, prf

def save_wms_image(filepath, **kwargs
                    ):
    img, prf=fetch_wms_image(**kwargs)

    # open img with rasterio as mem file
    
    with rio.open(filepath, "w", **prf) as dst:
        dst.write(img)
    if np.all(np.std(img, axis=(1,2))==0):
        print("Image data has zero standard deviation, indicating no variation in pixel values.")
    
    return img, prf
    


def get_least_cloudiest_image_for_region_and_timespan(wgs84_bounds, timespan):
    boundscrs="EPSG:4326"
    # https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/31/T/CK/2025/4/S2C_31TCK_20250407_0_L2A/TCI.tif
    
    
    
    df=gpd.GeoDataFrame(
        geometry=[shapely.geometry.box(*wgs84_bounds)],
        crs=boundscrs,
    ).to_crs("EPSG:4326")
    # os.makedirs(out_dir, exist_ok=True)
    # df.to_file(f"{out_dir}/aoi.geojson", driver="GeoJSON")
    
    res=stacSearch(df.unary_union,*timespan)
    
    cloudkeys=["s2:thin_cirrus_percentage","s2:high_proba_clouds_percentage","s2:medium_proba_clouds_percentage","s2:cloud_shadow_percentage"]
    res.sort(key=lambda x: np.sum([x["properties"][k] for k in cloudkeys]))
    
    r0=SimpleNamespace(**res[0])
    return r0, df

def test_least_cloudiest_rgb_image_for_region_and_timespan(wgs84_bounds, timespan,wms_url,layer):
    """_summary_

    Args:
        wgs84_bounds
        timespan
        wms_url
        layer

    Returns:
        corr: correlation coefficient between the two images
        p: p-value of the correlation
        np.sum(ind): number of pixels with valid data
    1. Fetch the least cloudiest image for the given region and timespan.
    2. Fetch the WMS image for the same region and timespan.
    3. Compare the two images by calculating the Pearson correlation coefficient.
    4. Return the correlation coefficient, p-value, and number of pixels with valid data.
    """
    r0, df=get_least_cloudiest_image_for_region_and_timespan(wgs84_bounds, timespan)
    
    p=r0.properties
    img_epsg=p["proj:epsg"]
    ass=r0.assets
    red=ass["red"]
    blue=ass["blue"]
    green=ass["green"]
    imgcrs=f"epsg:{img_epsg}"
    df_img=df.to_crs(imgcrs)
    img_df_geom=df_img.union_all()
    bb=img_df_geom.bounds
    res_in_m=10
    
    # d, prf=save_wms_image(bbox=bb, crs=imgcrs,
    #         start=datetime.strptime(p["datetime"][:10], "%Y-%m-%d").date(),
    #         res=res_in_m,
    #         wms_url=wms_url,
    #         layer=layer,
    #         filepath=f"{out_dir}/{out_dir}_geoserver_rgb.tif")
    
    d, prf=fetch_wms_image(bbox=bb, dst_crs=imgcrs,
            start=datetime.strptime(p["datetime"][:10], "%Y-%m-%d").date(),
            res=res_in_m,
            wms_url=wms_url,
            layer=layer)
    
    window= rio.windows.from_bounds(*bb, transform=Affine(*blue["proj:transform"]))
    
    with rio.open(blue["href"]) as blue_img, \
         rio.open(red["href"]) as red_img, \
         rio.open(green["href"]) as green_img:
        
        # Read the blue, red, and green band data
        blue_data = blue_img.read(1, window=window)
        red_data = red_img.read(1, window=window)
        green_data = green_img.read(1, window=window)
        prf2 = blue_img.profile
    
    # Create transform from window
    rgb_transform = Affine(*blue["proj:transform"]) * Affine.translation(window.col_off, window.row_off)
    
    prf2.update({
        "driver": "GTiff",
        "transform": rgb_transform,
        "height": window.height,
        "width": window.width,
        "count": 3  # Update to 3 bands for RGB
    })
    
    d2=np.stack(
        [red_data, green_data, blue_data],
        axis=0
        )
    # with rio.open(f"{out_dir}/aws_rgb.tif", "w", **prf2) as dst:
    #     dst.write(d2)
        
    
    ind=np.all(d>0, axis=0)
    mean1=np.mean(d[:,ind], axis=(1))[:3]
    mean2=np.mean(d2[:,ind], axis=(1))
    std1=np.std(d[:,ind], axis=(1))[:3]
    std2=np.std(d2[:,ind], axis=(1))
    
    #transform d to d2
    d1=d[:3,:,:]
    d1=d1-mean1[:, np.newaxis, np.newaxis]
    d1=d1/std1[:, np.newaxis, np.newaxis]
    d1=d1*std2[:, np.newaxis, np.newaxis]
    d1=d1+mean2[:, np.newaxis, np.newaxis]
    d1[:,~ind]=0
    d2[:,~ind]=0
    
    corr,p=pearsonr(d1[0,ind].flatten(), d2[0, ind].flatten())
    
    return float(corr), float(p), int(np.sum(ind))
    
    
    
    

if __name__=="__main__":
    #org prod bug:
    # timespan=date(2023, 2, 7),date(2023, 2, 9)
    # bounds=1031282.9537851777,6905262.24056703,1033376.9708029745,6906255.576872336
    # boundscrs="EPSG:3857"
    
    #prod
    out_dir="prod"
    # wms_url="https://api.coramaps.com/geoserver/wms?SERVICE=WMS&api-key=d13099a6-093a-4c98-b11c-f1c7026c3383&"
    wms_url="https://api.coramaps.com/wms?SERVICE=WMS&api-key=d86214ca-bcc0-45fd-8c2c-c27c414cb652&"
    layer="coramaps:s2_rgb"
    # layer="coramaps:s2_ndvi"
    
    # #test
    out_dir="test"
    # I get 2025_03_17
    wms_url="http://localhost:8085/geoserver/ows?SERVICE=WMS&"
    layer="myw:tci"
    # layer="myw:ndvi"
    # layer="myw:onetci"
    	
    timespan=date(2025, 4, 6),date(2025, 4, 8)
    bounds=0.748182,44.6840129,0.7618833,44.69329
    
    corr, p, num_pixels =test_least_cloudiest_rgb_image_for_region_and_timespan(wgs84_bounds=bounds,
        timespan=timespan,
        wms_url=wms_url,
        layer=layer
        )
    assert corr > 0.9, f"Correlation is too low: {corr}"
    assert p < 0.05, f"P-value is too high: {p}"
    assert num_pixels > 100, f"Number of valid pixels is too low: {num_pixels}"
    # return corr, p, num_pixels
    
    