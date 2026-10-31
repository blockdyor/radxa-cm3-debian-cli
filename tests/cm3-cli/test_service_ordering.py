"""Offline unit declaration checks, not proof of running services or host policy."""
import configparser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2] / 'packages/cm3-cli-board-support/root'
UNITS = ROOT / 'usr/lib/systemd/system'


def unit(path):
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    with path.open() as stream:
        config.read_file(stream)
    return config


class ServiceOrderingTests(unittest.TestCase):
    def test_ssh_requires_successful_enrollment_and_firewall_before_start(self):
        # /etc is intentional: this gate must override vendor drop-ins of the same name.
        gate = unit(ROOT / 'etc/systemd/system/ssh.service.d/cm3-cli.conf')['Unit']
        for directive in ['Requires', 'After']:
            self.assertLessEqual({'cm3-cli-enroll.service', 'cm3-cli-firewall.service'},
                                 set(gate[directive].split()), directive)

    def test_network_manager_requires_firewall_before_start(self):
        gate = unit(UNITS / 'NetworkManager.service.d/cm3-cli.conf')['Unit']
        for directive in ['Requires', 'After']:
            self.assertIn('cm3-cli-firewall.service', gate[directive].split(), directive)
        self.assertIn('systemd-networkd.service', gate['Conflicts'].split())

    def test_enrollment_requires_firewall_and_apparmor_before_start(self):
        enrollment = unit(UNITS / 'cm3-cli-enroll.service')
        for directive in ['Requires', 'After']:
            self.assertLessEqual({'cm3-cli-firewall.service', 'apparmor.service'},
                                 set(enrollment['Unit'][directive].split()), directive)
        self.assertIn('local-fs.target', enrollment['Unit']['After'].split())
        self.assertIn('ssh.service', enrollment['Unit']['Before'].split())
        self.assertEqual(enrollment['Service']['Type'], 'oneshot')
        self.assertTrue(enrollment['Service'].getboolean('RemainAfterExit'))

    def test_firewall_precedes_network_and_remains_installed_on_stop(self):
        firewall = unit(UNITS / 'cm3-cli-firewall.service')
        self.assertFalse(firewall.getboolean('Unit', 'DefaultDependencies'))
        self.assertIn('local-fs.target', firewall['Unit']['After'].split())
        self.assertLessEqual({'network-pre.target', 'shutdown.target'},
                             set(firewall['Unit']['Before'].split()))
        self.assertIn('network-pre.target', firewall['Unit']['Wants'].split())
        self.assertLessEqual({'nftables.service', 'shutdown.target'},
                             set(firewall['Unit']['Conflicts'].split()))
        self.assertEqual(firewall['Service']['Type'], 'oneshot')
        self.assertTrue(firewall['Service'].getboolean('RemainAfterExit'))
        self.assertEqual(firewall['Service']['ExecStart'].split(),
                         ['/usr/sbin/nft', '-f', '/usr/share/cm3-cli/firewall.nft'])
        self.assertNotIn('ExecStop', firewall['Service'])
        self.assertNotIn('ExecStopPost', firewall['Service'])


if __name__ == '__main__':
    unittest.main()
