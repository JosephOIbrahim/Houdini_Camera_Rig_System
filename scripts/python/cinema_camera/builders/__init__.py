"""
Cinema Camera Rig v4.0 -- Synapse Builder Scripts

Executed through the Synapse bridge in live Houdini sessions.
Each builder creates one HDA and saves it to disk.
"""

from .build_camera_rig_lop import build_camera_rig_lop_hda
from .build_chops_biomechanics import build_chops_biomechanics_hda
from .build_cop_anamorphic_flare import build_cop_anamorphic_flare_hda
from .build_cop_sensor_noise import build_cop_sensor_noise_hda
from .build_cop_stmap_aov import build_cop_stmap_aov_hda
from .parm_templates import build_camera_rig_parm_templates

__all__ = [
    "build_camera_rig_lop_hda",
    "build_camera_rig_parm_templates",
    "build_chops_biomechanics_hda",
    "build_cop_anamorphic_flare_hda",
    "build_cop_sensor_noise_hda",
    "build_cop_stmap_aov_hda",
]
