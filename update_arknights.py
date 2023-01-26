import sys
print(sys.path)

import util
import resource
from resource.arknights import ArknightsResource

ArknightsResource.start()
