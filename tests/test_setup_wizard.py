"""Offline setup-wizard tests. Do not require root, systemd, Podman or a Pi."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('spotifytouch_setup',ROOT/'scripts/setup.py')
setup=importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_reject_invalid_configuration(self):
        for bad in ['a@b','localhost:18080','127.0.0.1; touch /tmp/x','']:
            with self.assertRaises(RuntimeError): setup.validate_host(bad)
        with self.assertRaises(RuntimeError):setup.validate_user('some user')
        with self.assertRaises(RuntimeError):setup.validate_mac('not-a-mac')
        with self.assertRaises(RuntimeError):setup.validate_stream('https://example.com:18080/spotify.ts')
        with self.assertRaises(RuntimeError):setup.validate_stream('http://a:18080/spotify.ts?token=secret')
        self.assertEqual(setup.validate_mac('aa:bb:cc:dd:ee:ff'),'AA:BB:CC:DD:EE:FF')

    def test_unit_templates_are_local_and_on_demand(self):
        container=setup.unit_ubuntu_container('spotify-headless')
        self.assertIn('ExecStart=/usr/bin/podman start --attach spotify-headless',container)
        self.assertIn('WantedBy=default.target',container)
        api=setup.unit_ubuntu()
        self.assertIn('EnvironmentFile=%h/.config/spotifytouch/ubuntu.env',api)
        self.assertIn('WorkingDirectory=%h/.local/share/spotifytouch/ubuntu',api)
        audio=setup.unit_pi_audio('http://ubuntu.example.lan:18080/spotify.ts')
        self.assertNotIn('[Install]',audio)
        self.assertIn('--cache=no',audio)
        tunnel=setup.unit_pi_tunnel('spotify','ubuntu.example.lan','/home/pi/.ssh/id_ed25519')
        self.assertIn('BatchMode=yes',tunnel)
        self.assertIn('StrictHostKeyChecking=yes',tunnel)
        self.assertIn('-L 127.0.0.1:16080:127.0.0.1:16080',tunnel)

    def test_magicmirror_module_addition_is_conservative(self):
        before='let config = { modules: [\n {module: "clock"},\n] };\nmodule.exports = config;'
        after=setup.inject_magicmirror_module(before)
        self.assertIn('module: "MMM-SpotifyTouch"',after)
        self.assertEqual(setup.inject_magicmirror_module(after),after)
        with self.assertRaises(RuntimeError):setup.inject_magicmirror_module('let config={};')

    def test_transaction_restores_existing_files_without_systemd(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            tx=setup.Transaction.__new__(setup.Transaction)
            tx.role='pi';tx.folder=root/'backups';tx.entries=[];tx.units={}
            tx.container_created=None;tx.container_bridge=None
            dst=root/'config.css';dst.write_text('previous')
            tx.save(dst,'updated')
            tx.save(root/'new.txt','new')
            self.assertEqual(dst.read_text(),'updated')
            tx.rollback(restore_units=False)
            self.assertEqual(dst.read_text(),'previous')
            self.assertFalse((root/'new.txt').exists())

    def test_both_wrappers_dry_run_without_writing_files(self):
        checks=[['bash','scripts/install-ubuntu.sh','--dry-run','--container-mode','existing','--container','spotify-headless'],
                ['bash','scripts/install-pi.sh','--dry-run','--profile','standalone','--ssh-host','ubuntu.example.lan','--ssh-user','spotify'],
                ['bash','scripts/install-pi.sh','--dry-run','--profile','companion','--ssh-host','ubuntu.example.lan','--ssh-user','spotify']]
        for command in checks:
            p=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('DRY RUN: no changes made.',p.stdout)


if __name__=='__main__':unittest.main()