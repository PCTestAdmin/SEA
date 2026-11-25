import json
from pathlib import Path
import tempfile
import unittest
from sea.setup import entry, media_root, register, doctor


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.media = self.root / 'media'
        self.media.mkdir()
        self.config = self.root / 'client' / 'config.json'

    def write(self, raw):
        self.config.parent.mkdir(exist_ok=True)
        self.config.write_bytes(raw)

    def test_preview_does_not_write(self):
        self.assertEqual(register(self.config, self.media)['status'], 'preview')
        self.assertFalse(self.config.parent.exists())

    def test_create_and_repeat(self):
        self.assertEqual(register(self.config, self.media, apply=True)['status'], 'configured')
        self.assertEqual(json.loads(self.config.read_text())['mcpServers']['sea'], entry(self.media))
        self.assertEqual(register(self.config, self.media, apply=True)['status'], 'unchanged')
        self.assertFalse(list(self.config.parent.glob('*.bak')))

    def test_preserve_and_backup(self):
        original = b'{"mcpServers":{"other":{"command":"custom","env":{"TOKEN":"SEA_TEST_SECRET_8274"}}},"theme":"dark"}\n'
        self.write(original)
        result = register(self.config, self.media, apply=True)
        self.assertEqual(Path(result['backup']).read_bytes(), original)
        current = json.loads(self.config.read_text())
        self.assertEqual(current['mcpServers']['other'], json.loads(original)['mcpServers']['other'])
        self.assertEqual(current['theme'], 'dark')
        self.assertNotIn('SEA_TEST_SECRET_8274', json.dumps(result))

    def test_conflict(self):
        original = b'{"mcpServers":{"sea":{"command":"different"}}}'
        self.write(original)
        with self.assertRaises(ValueError):
            register(self.config, self.media, apply=True)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(register(self.config, self.media, apply=True, replace=True)['status'], 'configured')

    def test_invalid_configs(self):
        for raw in (b'broken', b'[]', b'{"mcpServers":[]}', b'{"a":1,"a":2}'):
            self.write(raw)
            with self.assertRaises(ValueError):
                register(self.config, self.media, apply=True)
            self.assertEqual(self.config.read_bytes(), raw)
        self.assertFalse(list(self.config.parent.glob('*.bak')))

    def test_media_root(self):
        self.assertEqual(media_root(str(self.media)), self.media)
        with self.assertRaises(ValueError):
            media_root(str(Path.home()))
        with self.assertRaises(FileNotFoundError):
            media_root(str(self.root / 'absent'))

    def test_doctor(self):
        self.assertEqual(doctor(self.media)['version'], '0.4.0')
        self.assertTrue(doctor(self.media)['checks']['media_root'])
