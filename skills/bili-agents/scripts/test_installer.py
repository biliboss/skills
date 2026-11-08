import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('install', Path(__file__).parents[1] / 'app/herdr-bots/install.py')
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'instance'
        self.folder.mkdir()
        (self.folder / '.memory').write_bytes(b'old content\x00\xff')
        (self.folder / 'link').symlink_to('.memory')
        self.bot = {'id': 'test', 'folder': str(self.folder), 'session_id': '00000000-0000-4000-8000-000000000001'}
        patcher = patch.object(install.bots, 'HOME', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_backup_preserves_bytes_and_symlinks_and_reinstall_preserves_new_content(self):
        with patch.object(install.subprocess, 'run') as run, patch.object(install.bots, 'call', return_value={'terminals': []}):
            run.return_value.returncode = 0
            run.return_value.stdout = 'p1\nn/unrelated\n'
            install.prepare(self.bot)
            backup, = self.root.glob('instance.backup-*')
            self.assertEqual((backup / '.memory').read_bytes(), b'old content\x00\xff')
            self.assertTrue((backup / 'link').is_symlink())
            self.assertEqual((self.folder / 'AGENTS.md').read_text(), '')
            self.assertEqual((self.folder / 'CLAUDE.md').read_text(), '@AGENTS.md\n')
            self.assertFalse((self.folder / '.memory').exists())
            (self.folder / 'new').write_text('keep')
            install.prepare(self.bot)
            self.assertEqual((self.folder / 'new').read_text(), 'keep')
            self.assertEqual(len(list(self.root.glob('instance.backup-*'))), 1)

    def test_active_process_blocks_without_changes(self):
        with patch.object(install.subprocess, 'run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = 'p1\nn' + str(self.folder.resolve()) + '\n'
            with self.assertRaisesRegex(RuntimeError, 'active process'):
                install.prepare(self.bot)
        self.assertTrue((self.folder / '.memory').exists())
        self.assertEqual(list(self.root.glob('instance.backup-*')), [])


if __name__ == '__main__':
    unittest.main()
