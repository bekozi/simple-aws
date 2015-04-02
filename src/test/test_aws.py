import unittest
import itertools
from aws import AwsManager
import os


CONF_PATH = os.path.join(os.path.expanduser('~/.config/simple-aws.conf'))


class TestAwsManager(unittest.TestCase):
    PREFIX = '_test_simple_aws_'

    @classmethod
    def tearDownClass(cls):
        m = AwsManager(CONF_PATH)
        instances = m.get_instances(key='name')
        for key in instances.iterkeys():
            assert not key.startswith(cls.PREFIX)

    @property
    def iname(self):
        return self.get_instance_name('foo')

    def get_instance_name(self, suffix):
        return '{0}{1}'.format(self.PREFIX, suffix)

    def test_init(self):
        filtered = [True, False]
        only_running = [True, False]
        conf_path = [None, CONF_PATH]
        for f, a, c in itertools.product(filtered, only_running, conf_path):
            try:
                m = AwsManager(c, filtered=f, only_running=a)
                self.assertIsInstance(m._cfg, dict)
            except ValueError:
                if c is None:
                    pass
                else:
                    raise

    def test_get_instance_by_name(self):
        m = AwsManager(CONF_PATH)
        i1 = m.launch_new_instance(self.iname, wait=True)
        try:
            instance = m.get_instance_by_name(self.iname)
            self.assertEqual(instance.tags['Name'], self.iname)
        finally:
            i1.terminate()

    def test_start_instance_by_name(self):
        m = AwsManager(CONF_PATH)
        i1 = m.launch_new_instance(self.iname, wait=True)
        try:
            i1.stop()
            AwsManager.wait_for_status(i1, 'stopped', pad=20)
            instance = m.start_instance_by_name(self.iname)
            self.assertEqual(instance.update(), 'running')
        finally:
            i1.terminate()

    def test_launch_instance_with_wait(self):
        m = AwsManager(CONF_PATH)
        # print('launching 1')
        name1 = self.get_instance_name('foo_test_1')
        i1 = m.launch_new_instance(name1)
        # print('launching 2')
        i2 = m.launch_new_instance(self.get_instance_name('foo_test_2'))
        # print('instances launched')
        try:
            self.assertEqual(i1.update(), 'running')
            self.assertEqual(i2.update(), 'running')
        finally:
            i1.terminate()
            i2.terminate()

    def test_launch_instance_without_wait(self):
        m = AwsManager(CONF_PATH)
        i1 = m.launch_new_instance(self.iname, wait=False)
        try:
            self.assertNotEqual(i1.update(), 'running')
        finally:
            i1.terminate()

    def test_launch_new_instance_elastic_ip(self):
        elastic_ip = '54.68.61.218'
        m = AwsManager(CONF_PATH)
        name = self.get_instance_name('foo_test_elastic_ip')
        i1 = m.launch_new_instance(name, elastic_ip=elastic_ip)
        try:
            self.assertEqual(i1.ip_address, elastic_ip)
        finally:
            i1.terminate()

    def test_name_must_be_unique(self):
        m = AwsManager(CONF_PATH)
        name = self.get_instance_name('foo_unique')
        try:
            i1 = m.launch_new_instance(name, wait=True)
            with self.assertRaises(ValueError):
                i2 = m.launch_new_instance(name, wait=True)
        finally:
            try:
                i1.terminate()
                i2.terminate()
            except UnboundLocalError:
                pass

    def test_send_email(self):
        raise unittest.SkipTest('development only')
        fromaddr = 'benkoziol@gmail.com'
        recipient = 'benkoziol@gmail.com'
        subject = 'OCGIS_AWS'
        body = 'This is some email content.'
        m = AwsManager(CONF_PATH)
        m.send_email(fromaddr, recipient, subject, body)
