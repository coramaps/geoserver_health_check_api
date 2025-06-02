
import argparse
from configparser import ConfigParser
from itertools import cycle
import abc
from datetime import datetime, timedelta, date
import hashlib
from logging import handlers
import geopandas as gpd
from pathlib import Path
import random
import json
import logging
from math import ceil, floor
import os
import socket
from typing import ClassVar, Literal
import pystac_client
import shapely
import shutil
import time
import warnings
from zipfile import BadZipFile, ZipFile
import numpy as np
import requests
from threading import Thread
import tqdm
import sys
import os
sys.path.append(os.getcwd())
from api import CONFIG

def getMetadataFromOpenSearch(
    start, end,
    endpoint: str="https://catalogue.dataspace.copernicus.eu/resto/api/collections/Sentinel2/search.json",
    chunksizeInDays=10,
    boundsWGS84=None,
    aoiWGS84=None,
    additionalRequestParams={"productType": "L2A"},
    nTries=5,
):
    if boundsWGS84 is None:
        b = aoiWGS84.bounds
        tolerance = np.mean([b[2] - b[0], b[3] - b[1]]) / 100
        aoi = aoiWGS84.simplify(tolerance=tolerance)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            aoi = aoi.buffer(tolerance, resolution=2)
        boundsWGS84 = [str(x) for x in aoi.bounds]

    def getFeaturesForTimespan(startDate, endDate):
        if isinstance(startDate, datetime):
            startDate = date(startDate.year, startDate.month, startDate.day)
        if isinstance(endDate, datetime):
            endDate = date(endDate.year, endDate.month, endDate.day)
        params = {
            # "geometry": aoi,
            "startDate": f"{startDate.isoformat()}T00:00:00Z",
            "completionDate": f"{endDate.isoformat()}T23:59:59Z",
            "box": ",".join(boundsWGS84),
            "maxRecords": 200,
            "sortParam": "startDate",
            "sortOrder": "descending",
            **additionalRequestParams,
        }

        search_api_results = None
        with requests.Session() as s:
            features = []
            ix = 1
            nextPage = True
            nextLink = None

            while nextPage:
                params["page"] = ix
                for i in range(nTries):
                    if nextLink is not None:
                        res = s.get(nextLink)
                    else:
                        res = s.get(endpoint, params=params)
                    if res.status_code == 200:
                        search_api_results = res.json()
                    else:
                        time.sleep(1)
                        if (i + 1) < nTries:
                            continue
                        raise requests.RequestException(f"{res.text}: {res.status_code}")
                    if ix == 1:
                        n = search_api_results["properties"]["totalResults"]
                    break
                    
                _features = search_api_results["features"]
                features.extend(_features)
                ix = ix + 1
                nextPage = len(search_api_results["features"]) > 0

                if nextPage:
                    nextLink = [
                        x["href"]
                        for x in search_api_results["properties"]["links"]
                        if x["title"] == "next"
                    ]
                    if len(nextLink) == 0:
                        nextLink = None
                    else:
                        nextLink = nextLink[0]

            if n:
                if n != len(features):
                    raise AssertionError(f"Different number of features are found ({n}) and are existing ({len(features)}).")

            ids = []
            _features = []
            for f in features:
                if f["id"] in ids:
                    duplicates = [ff for ff in _features if f["id"] == ff["id"]]
                    strs = [json.dumps(d) for d in duplicates]
                    s2 = json.dumps(f)
                    for s in strs:
                        if s2 == s:
                            continue
                        logging.error(f"Duplicate ID {f['id']} for different features:")
                        logging.error(s)
                        logging.error(s2)
                        raise AssertionError(
                            f"Duplicate ID {f['id']} for different features."
                        )
                else:
                    _features.append(f)
                    ids.append(f["id"])

        if search_api_results is None:
            raise AssertionError("something went wrong")
        return _features

    startDate = start
    endDate = startDate + timedelta(days=chunksizeInDays)
    feats = []
    with tqdm.tqdm(
        desc="fetching metadata [days]", total=ceil((end - start).days)
    ) as pbar:
        while startDate <= end:
            feats += getFeaturesForTimespan(startDate, min(endDate, end))
            startDate = startDate + timedelta(days=chunksizeInDays + 1)
            endDate = startDate + timedelta(days=chunksizeInDays)
            pbar.update(chunksizeInDays)

    def getAoi(feature):
        if "geometry" in feature:
            return shapely.geometry.shape(feature["geometry"])

        # try to get geometry from the gmlgeometry:
        p = feature["properties"]
        aoi = None
        if "EPSG:4326" not in p["gmlgeometry"]:
            raise ValueError("Coordinate system changed from WGS84 to sth else.")
        # find coordinates in gml feature
        if p["gmlgeometry"].count("<gml:coordinates>") == 1:
            coords = p["gmlgeometry"].split("<gml:coordinates>")[1].split("</gml:coordinates>")[0]
            # create geojson
            aoi = {
                "type": "Polygon",
                "coordinates": [[[float(x) for x in p.split(",")] for p in coords.split(" ")]],
            }
        else:
            # pull geojson from link (is slow)
            for l in p["links"]:
                if l["type"] == "application/json":
                    r = requests.get(l["href"]).json()
                    aoi = r["geometry"]
        if aoi:
            aoi = shapely.geometry.shape(aoi)
        else:
            raise ValueError(f"could not generate area of interest for image {feature['id']}")
        return aoi

    res = []
    for f in feats:
        f["geometry"] = getAoi(f)
        if aoiWGS84 is not None:
            if not f["geometry"].intersects(aoiWGS84):
                continue
        res.append(f)
    return res

def stacSearch(bounds, startDate, endDate, limit=250, query={},endpoint=None):
    if endpoint is None:
        endpoint=CONFIG.get("S3_BUCKET","ENDPOINT_S2")
    logging.info(f"StartDate: {startDate}, EndDate: {endDate}")
    # read endpoint of STAC:
    stac = pystac_client.Client.open(endpoint)

    # define search params
    search = stac.search(
            intersects=bounds,
            limit=limit,
            datetime=f"{startDate.isoformat()}/{endDate.isoformat()}",
            collections=['sentinel-2-l2a'],
            query=query,
            method='POST',
            max_items=None
            )
    logging.info(f"Number of results on server: {search.matched()}")
    # execute search and get results
    items = []
    for elem in search.items_as_dicts():
        items.append(elem)
    # items = list(search.get_items())
    # items = [i.to_dict() for i in items]
    logging.info(f"Retrieved {len(items)} items!")
    return items





if __name__=="__main__":
    bounds=1031282.9537851777,6905262.24056703,1033376.9708029745,6906255.576872336
    df=gpd.GeoDataFrame(
        geometry=[shapely.geometry.box(*bounds)],
        crs="EPSG:3857",
    ).to_crs("EPSG:4326")
    
    res=stacSearch(df.unary_union,date(2022, 1, 1),date(2023, 2, 1))
    res[0]
    json.dump(res[0], indent=4, fp=open("test.json", "w"))
    o=1