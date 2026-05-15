# Cinema Camera Rig v4.0 -- Camera Body Providers
#
# Importing this package auto-registers all bundled body providers
# (via side-effect imports below). All six 2026 professional cinema
# bodies surface through cinema_camera.registry.get_body(<id>).

from . import alexa35                       # noqa: F401  -- "arri_alexa_35"
from . import alexa_mini_lf                  # noqa: F401  -- "arri_alexa_mini_lf"
from . import alexa_65                       # noqa: F401  -- "arri_alexa_65"
from . import sony_venice_2                  # noqa: F401  -- "sony_venice_2"
from . import red_v_raptor_8k_vv             # noqa: F401  -- "red_v_raptor_8k_vv"
from . import blackmagic_ursa_cine_12k_lf    # noqa: F401  -- "blackmagic_ursa_cine_12k_lf"
