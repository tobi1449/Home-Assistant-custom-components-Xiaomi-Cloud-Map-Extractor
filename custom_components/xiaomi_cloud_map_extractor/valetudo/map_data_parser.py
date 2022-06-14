import json
import logging
from typing import Tuple

from custom_components.xiaomi_cloud_map_extractor.common.map_data import (
    Area,
    MapData,
    Path,
    Point,
    Room,
    Wall,
    ImageData,
)
from custom_components.xiaomi_cloud_map_extractor.common.map_data_parser import (
    MapDataParser,
)
from custom_components.xiaomi_cloud_map_extractor.valetudo.image_handler import (
    ImageHandlerValetudo,
)

_LOGGER = logging.getLogger(__name__)


class MapDataParserValetudo(MapDataParser):
    @staticmethod
    def map_to_image(p: Point, pixel_size: int) -> Point:
        return Point(p.x / pixel_size, p.y / pixel_size)

    @staticmethod
    def parse_points(coordinates, pixel_size) -> list[Point]:
        points = []

        for index in range(0, len(coordinates), 2):
            points.append(
                MapDataParserValetudo.map_to_image(
                    Point(coordinates[index], coordinates[index + 1]), pixel_size
                )
            )

        return points

    @staticmethod
    def parse_point_map_entity(entity, pixel_size) -> Point:
        return MapDataParserValetudo.map_to_image(
            Point(
                entity["points"][0], entity["points"][1], entity["metaData"]["angle"]
            ),
            pixel_size,
        )

    @staticmethod
    def parse_polygon_map_entity(entity, pixel_size) -> Area:
        points = MapDataParserValetudo.parse_points(entity["points"], pixel_size)

        return Area(
            points[0].x,
            points[0].y,
            points[1].x,
            points[1].y,
            points[2].x,
            points[2].y,
            points[3].x,
            points[3].y,
        )

    @staticmethod
    def parse_line_map_entity(entity, pixel_size) -> Wall:
        points = MapDataParserValetudo.parse_points(entity["points"], pixel_size)

        return Wall(points[0].x, points[0].y, points[1].x, points[1].y)

    @staticmethod
    def decompress_pixels(compressed_pixels: list[int]) -> list[int]:
        pixels = []
        for i in range(0, len(compressed_pixels), 3):
            x_start = compressed_pixels[i]
            y = compressed_pixels[i + 1]
            count = compressed_pixels[i + 2]
            for j in range(0, count):
                pixels.append(x_start + j)
                pixels.append(y)
        return pixels

    @staticmethod
    def parse_walls(layer) -> list[int]:
        return MapDataParserValetudo.decompress_pixels(layer["compressedPixels"])

    @staticmethod
    def parse_room(layer) -> Tuple[Room, list[int]]:

        dimensions = layer["dimensions"]
        meta_data = layer["metaData"]
        name = None
        if "name" in meta_data:
            name = meta_data["name"]
        segment_id = int(meta_data["segmentId"])
        xmin = dimensions["x"]["min"]
        xmax = dimensions["x"]["max"]
        ymin = dimensions["y"]["min"]
        ymax = dimensions["y"]["max"]

        return Room(
            segment_id,
            xmin,
            ymin,
            xmax,
            ymax,
            name,
        ), MapDataParserValetudo.decompress_pixels(layer["compressedPixels"])

    @staticmethod
    def parse_path_map_entity(entity, pixel_size) -> Path:
        return Path(
            None,
            None,
            None,
            [MapDataParserValetudo.parse_points(entity["points"], pixel_size)],
        )

    @staticmethod
    def decode_map(
        raw_map: str, colors, drawables, texts, sizes, image_config
    ) -> MapData:
        _LOGGER.debug(f"decoding map")

        map_data = MapData()
        map_data.no_go_areas = []
        map_data.no_mopping_areas = []
        map_data.walls = []
        map_data.rooms = []

        map_object = json.loads(raw_map)

        pixel_size = 1 #int(map_object["pixelSize"])

        for entity in map_object["entities"]:
            if entity["type"] == "robot_position":
                map_data.vacuum_position = MapDataParserValetudo.parse_point_map_entity(
                    entity, pixel_size
                )
            elif entity["type"] == "charger_location":
                map_data.charger = MapDataParserValetudo.parse_point_map_entity(
                    entity, pixel_size
                )
            elif entity["type"] == "no_go_area":
                map_data.no_go_areas.append(
                    MapDataParserValetudo.parse_polygon_map_entity(entity, pixel_size)
                )
            elif entity["type"] == "no_mop_area":
                map_data.no_mopping_areas.append(
                    MapDataParserValetudo.parse_polygon_map_entity(entity, pixel_size)
                )
            elif entity["type"] == "virtual_wall":
                map_data.walls.append(
                    MapDataParserValetudo.parse_line_map_entity(entity, pixel_size)
                )
            elif entity["type"] == "path":
                map_data.path = MapDataParserValetudo.parse_path_map_entity(
                    entity, pixel_size
                )

        walls = []
        rooms = []
        for layer in map_object["layers"]:
            if layer["type"] == "wall":
                walls = MapDataParserValetudo.parse_walls(layer)
            elif layer["type"] == "segment":
                rooms.append(MapDataParserValetudo.parse_room(layer))

        map_data.rooms = dict(map(lambda x: (x[0].number, x[0]), rooms))

        image = ImageHandlerValetudo.draw(
            walls,
            rooms,
            map_object["size"]["x"],
            map_object["size"]["y"],
            colors,
            image_config,
        )

        box = image.getbbox()
        image = image.crop(box)

        width, height = image.size
        map_data.image = ImageData(
            width * height,
            0,
            0,
            height,
            width,
            image_config,
            image,
            lambda p: MapDataParserValetudo.map_to_image(p, pixel_size),
        )

        MapDataParserValetudo.draw_elements(
            colors, drawables, sizes, map_data, image_config
        )

        return map_data
