import unittest
import itertools
from aws import AwsManager
import os


CONF_PATH = os.path.join(os.path.expanduser('~/.config/simple-aws.conf'))


class TestAwsManager(unittest.TestCase):

    @classmethod
    def tearDownClass(cls):
        m = AwsManager(CONF_PATH)
        assert(m.get_instances() == {})

    def test_constructor(self):
        filtered = [True, False]
        only_running = [True, False]
        conf_path = [None, CONF_PATH]
        for f, a, c in itertools.product(filtered, only_running, conf_path):
            try:
                m = AwsManager(c, filtered=f, only_running=a)
                self.assertIsInstance(m._cfg, dict)
            except TypeError:
                if c is None:
                    pass
                else:
                    raise

    def test_get_instance_by_name(self):
        m = AwsManager(CONF_PATH)
        i1 = m.launch_new_instance('_foo_name_test', wait=True)
        try:
            instance = m.get_instance_by_name('_foo_name_test')
            self.assertEqual(instance.tags['Name'], '_foo_name_test')
        finally:
            i1.terminate()

    def test_start_instance_by_name(self):
        m = AwsManager(CONF_PATH)
        i1 = m.launch_new_instance('_foo_name_test', wait=True)
        try:
            i1.stop()
            AwsManager.wait_for_status(i1, 'stopped')
            instance = m.start_instance_by_name('_foo_name_test')
            self.assertEqual(instance.update(), 'running')
        finally:
            i1.terminate()

    def test_launch_instance_with_wait(self):
        m = AwsManager(CONF_PATH)
        # print('launching 1')
        i1 = m.launch_new_instance('_foo_test_1')
        self.assertEqual(i1.tags['Name'], '_foo_test_1')
        # print('launching 2')
        i2 = m.launch_new_instance('_foo_test_2')
        # print('instances launched')
        try:
            instances = m.get_instances()
            self.assertEqual(len(instances), 2)
            self.assertEqual(set([i.update() for i in instances.values()]), set(['running']))
        finally:
            i1.terminate()
            i2.terminate()
        self.assertEqual(m.get_instances(), {})

    def test_launch_instance_without_wait(self):
        m = AwsManager(CONF_PATH)
        i1 = m.launch_new_instance('_foo_test_1', wait=False)
        try:
            self.assertNotEqual(i1.update(), 'running')
        finally:
            i1.terminate()
        self.assertEqual(m.get_instances(), {})

    def test_launch_new_instance_elastic_ip(self):
        elastic_ip = '54.68.61.218'
        m = AwsManager(CONF_PATH)
        name = '_foo_test_elastic_ip'
        i1 = m.launch_new_instance(name, elastic_ip=elastic_ip)
        try:
            self.assertEqual(i1.ip_address, elastic_ip)
        finally:
            i1.terminate()

    def test_name_must_be_unique(self):
        m = AwsManager(CONF_PATH)
        self.assertEqual(m.get_instances(), {})
        try:
            i1 = m.launch_new_instance('_foo_test_4', wait=True)
            with self.assertRaises(ValueError):
                i2 = m.launch_new_instance('_foo_test_4', wait=True)
        finally:
            try:
                i1.terminate()
                i2.terminate()
            except UnboundLocalError:
                pass
