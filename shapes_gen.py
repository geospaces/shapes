#!/usr/bin/env python
# -*- coding: utf-8 -*-

import osmium
import json
import os
from slugify import slugify
import shapely.wkb

import time
start = time.time()

COMARQUES = [
    "Anoia",
    "Bages",
    "Barcelonès",
    "Berguedà",
]

GEOFABRIK = "/opt/OSM/catalunya.osm.pbf"
OUT_BASE_DIR = "/catalunya/barcelona/"
wkb_factory = osmium.geom.WKBFactory()

# --------------------------------------------------
# 1. Geometries de comarques
# --------------------------------------------------
class AllComarques(osmium.SimpleHandler):
    def __init__(self, noms_comarques):
        super().__init__()
        self.noms_comarques = set(noms_comarques)
        self.geometries = {}

    def area(self, a):
        tags = a.tags
        nom = tags.get("name")

        if (tags.get("boundary") == "administrative"
            and tags.get("admin_level") == "7"
            and nom in self.noms_comarques):
            try:
                wkb = wkb_factory.create_multipolygon(a)
                self.geometries[nom] = shapely.wkb.loads(wkb, hex=True)
            except Exception:
                pass

# --------------------------------------------------
# 2. Municipis → GeoJSON directe
# --------------------------------------------------
class MunicipisToGeoJSON(osmium.SimpleHandler):
    def __init__(self, comarques_geom):
        super().__init__()
        self.comarques_geom = comarques_geom
        self.count = {nom: 0 for nom in comarques_geom.keys()}

    def area(self, a):
        tags = a.tags

        if tags.get("boundary") != "administrative":
            return

        if tags.get("admin_level") != "8":
            return

        nom_municipi = tags.get("name")
        if not nom_municipi:
            return

        try:
            # Geometria municipi
            wkb = wkb_factory.create_multipolygon(a)
            geom = shapely.wkb.loads(wkb, hex=True)

            # Assignació a comarca
            for comarca_nom, comarca_geom in self.comarques_geom.items():
                if geom.intersects(comarca_geom):
                    inter = geom.intersection(comarca_geom)

                    if inter.area / geom.area > 0.8:
                        slug_comarca = slugify(comarca_nom)
                        slug_municipi = slugify(nom_municipi)

                        # Crear carpeta comarca
                        comarca_dir = os.path.join(OUT_BASE_DIR, slug_comarca)
                        os.makedirs(comarca_dir, exist_ok=True)

                        # GeoJSON
                        feature = {
                            "type": "Feature",
                            "properties": {
                                "nom": nom_municipi,
                                "comarca": comarca_nom,
                                "wikidata": tags.get("wikidata", "")
                            },
                            "geometry": json.loads(
                                osmium.geom.GeoJSONFactory().create_multipolygon(a)
                            )
                        }

                        arxiu = os.path.join(comarca_dir, f"{slug_municipi}.geojson")

                        with open(arxiu, "w", encoding="utf-8") as f:
                            json.dump(feature, f, ensure_ascii=False)

                        self.count[comarca_nom] += 1
                        break

        except Exception:
            pass

# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == '__main__':
    os.makedirs(OUT_BASE_DIR, exist_ok=True)

    print("Pas 1: Extraient geometries de comarques...")
    comarques_handler = AllComarques(COMARQUES)
    comarques_handler.apply_file(GEOFABRIK, locations=True)

    print(f"Comarques trobades: {len(comarques_handler.geometries)}\n")

    print("Pas 2: Generant GeoJSON de municipis...")
    municipis_handler = MunicipisToGeoJSON(comarques_handler.geometries)
    municipis_handler.apply_file(GEOFABRIK, locations=True)

    print("\nResultats:")
    for comarca, n in municipis_handler.count.items():
        print(f"{comarca}: {n} municipis")

end = time.time()
print(f"\nTemps: {round(end-start, 2)}s")
