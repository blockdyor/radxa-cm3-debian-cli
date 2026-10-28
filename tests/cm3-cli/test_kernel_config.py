"""Kernel capability contract; no package compilation or target boot."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('source_preflight', ROOT / 'scripts/cm3-source-preflight.py')
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


class KernelConfigTests(unittest.TestCase):
    def setUp(self):
        self.builtin = '''BLK_DEV_INITRD RD_GZIP MODULES CGROUPS NAMESPACES UTS_NS
IPC_NS USER_NS PID_NS NET_NS SECCOMP SECCOMP_FILTER MULTIUSER SECURITY SECURITYFS
SECURITY_APPARMOR'''.split()
        self.modular = '''OVERLAY_FS BRIDGE BRIDGE_NETFILTER NETFILTER NF_TABLES TUN IPV6'''.split()
        self.settings = {f'CONFIG_{name}': 'y' for name in self.builtin}
        self.settings.update({f'CONFIG_{name}': 'm' for name in self.modular})

    def config(self, settings):
        return '\n'.join(f'{name}={value}' for name, value in settings.items()) + '\n'

    def test_builtin_and_modular_facilities_retained(self):
        source.verify_kernel_config(self.config(self.settings))
        settings = {name: 'y' for name in self.settings}
        source.verify_kernel_config(self.config(settings))

    def test_every_required_capability_fails_closed_when_disabled_or_missing(self):
        for name in self.settings:
            for value in ['n', None]:
                with self.subTest(name=name, value=value):
                    settings = self.settings.copy()
                    if value is None:
                        del settings[name]
                    else:
                        settings[name] = value
                    with self.assertRaisesRegex(ValueError, name):
                        source.verify_kernel_config(self.config(settings))

    def test_required_builtin_cannot_be_only_a_module(self):
        for name in self.builtin:
            settings = self.settings | {f'CONFIG_{name}': 'm'}
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, f'CONFIG_{name}'):
                source.verify_kernel_config(self.config(settings))

    def test_ambiguous_duplicate_configuration_rejected(self):
        text = self.config(self.settings) + 'CONFIG_SECCOMP=n\n'
        with self.assertRaisesRegex(ValueError, 'duplicate.*CONFIG_SECCOMP'):
            source.verify_kernel_config(text)

    def test_comments_and_unrelated_configuration_do_not_satisfy_contract(self):
        text = self.config(self.settings).replace('CONFIG_SECCOMP=y', '# CONFIG_SECCOMP is not set')
        text += 'CONFIG_UNRELATED=y\n'
        with self.assertRaisesRegex(ValueError, 'CONFIG_SECCOMP'):
            source.verify_kernel_config(text)


if __name__ == '__main__':
    unittest.main()
