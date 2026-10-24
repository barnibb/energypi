import sys
import types
import unittest
from unittest.mock import Mock,patch
from meross_dns import configure_meross_dns

class MerossDnsTests(unittest.TestCase):
 def test_scoped_idempotent_factory_and_connector(self):
  aio=types.ModuleType('aiohttp');resolver=types.ModuleType('aiohttp.resolver')
  meross=types.ModuleType('meross_iot');http=types.ModuleType('meross_iot.http_api')
  factory=Mock();http.ClientSession=factory;factory._energypi_system_dns=False
  meross.http_api=http;aio.ClientSession=Mock();aio.TCPConnector=Mock()
  resolver.ThreadedResolver=Mock()
  with patch.dict(sys.modules,{'aiohttp':aio,'aiohttp.resolver':resolver,'meross_iot':meross,'meross_iot.http_api':http}):
   configure_meross_dns();wrapped=http.ClientSession;configure_meross_dns()
   self.assertIs(http.ClientSession,wrapped)
   http.ClientSession()
   aio.TCPConnector.assert_called_once_with(resolver=resolver.ThreadedResolver.return_value)
   factory.assert_called_once_with(connector=aio.TCPConnector.return_value,connector_owner=True)
   aio.ClientSession.assert_not_called()
   connector=object();http.ClientSession(connector=connector)
   factory.assert_called_with(connector=connector)
   self.assertEqual(aio.TCPConnector.call_count,1)
