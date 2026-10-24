import struct
import unittest
from unittest.mock import Mock, patch

from marstek_diagnose import explain, format_text, read_snapshot, signed16


class DiagnoseTests(unittest.TestCase):
    def test_signed_schedule_power_and_meanings(self):
        self.assertEqual(signed16(65535), -1)
        self.assertEqual(signed16(2500), 2500)
        self.assertEqual(explain(42000, 21947), 'RS485-Steuerung freigegeben')
        self.assertEqual(explain(43000, 1), 'Eigenverbrauch')

    def test_snapshot_uses_read_function_only(self):
        values = {
            (32104, 1): (62,), (32202, 2): struct.unpack('>HH', struct.pack('>i', -500)),
            (42000, 1): (21947,), (42010, 1): (0,), (42011, 1): (80,),
            (42020, 1): (0,), (42021, 1): (0,), (43000, 1): (1,),
            (44000, 1): (800,), (44002, 1): (2500,), (44003, 1): (800,),
        }
        for slot in range(6):
            values[(43100 + slot * 5, 5)] = (127, 500, 2300, 65535, 0)

        def fake_read(sock, transaction, unit, address, count):
            return struct.pack('>' + 'H' * count, *values[(address, count)])

        connection = Mock()
        with patch('marstek_diagnose.socket.create_connection') as connector, \
             patch('marstek_diagnose.read_registers', side_effect=fake_read):
            connector.return_value.__enter__.return_value = connection
            snapshot = read_snapshot({'host': 'test', 'port': 502, 'unit': 1}, pause_seconds=0)
        self.assertEqual(snapshot['measurements']['ac_power_w'], -500)
        self.assertEqual(snapshot['schedules'][0]['power_signed_w'], -1)
        text = format_text(snapshot, 'Eigenverbrauch')
        self.assertIn('Nur gelesen: Modbus-Funktion 03', text)
        self.assertIn('43000  user_work_mode: 1  (Eigenverbrauch)', text)
