from pkg_resources import resource_filename
from gftools.axes_pb2 import AxisProto, FallbackProto
from gftools.utils import read_proto
from glob import glob
import os


__all__ = ["axis_registry"]


def AxisRegistry():
    """Parse all axes in the Google Fonts axis registry"""
    results = {}
    axis_reg_dir = resource_filename("gftools", "axisregistry")
    proto_files = glob(os.path.join(axis_reg_dir, "*.textproto"))
    for proto_file in proto_files:
        axis = read_proto(proto_file, AxisProto())
        results[axis.tag] = axis
        # Remove spaces from names
        for fallback in results[axis.tag].fallback:
            fallback.name = fallback.name.replace(" ", "")
    return results


axis_registry = AxisRegistry()
