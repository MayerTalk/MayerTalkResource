import os

from resource.arknights import ArknightsResource

ArknightsResource.start()

if ArknightsResource.push:
  os.system('git config --global user.email noreply@arkfans.top')
  os.system('git config --global user.name MeeBooBot_v0')
  os.system('git push')
