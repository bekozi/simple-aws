import unittest
import itertools
import os
from fabric.operations import run
from nose.plugins.attrib import attr
from saws import AwsManager
from saws.exc import InstanceNameNotAvailable
from saws.manager import AwsManagerConfiguration


CONF_PATH = os.path.join(os.path.expanduser('~/.config/simple-aws.conf'))

"""
nosetests -vs --nologcapture -a '!slow,!dev' saws/test
Attributes:
 - slow :: slow tests
 - dev :: development tests
"""

class AbstractTestSimpleAws(unittest.TestCase):
    prefix = '_test_simple_aws_'

    def __init__(self, *args, **kwargs):
        self.shared_instance_name = self.get_instance_name('shared')
        self._shared_instance = None
        super(AbstractTestSimpleAws, self).__init__(*args, **kwargs)

    @property
    def iname(self):
        return self.get_instance_name('foo')

    @property
    def shared_instance(self):
        if self._shared_instance is None:
            m = AwsManager(conf_path=CONF_PATH)
            self._shared_instance = m.launch_new_instance(self.shared_instance_name)
        return self._shared_instance

    @classmethod
    def get_instance_name(cls, suffix):
        return '{0}{1}'.format(cls.prefix, suffix)

    @classmethod
    def tearDownClass(cls):
        m = AwsManager(CONF_PATH)
        try:
            i = m.get_instance_by_name(cls.get_instance_name('shared'))
        except InstanceNameNotAvailable:
            pass
        else:
            i.terminate()
        instances = m.get_instances(key='name')
        for key in instances.iterkeys():
            assert not key.startswith(cls.prefix)


class TestAwsManager(AbstractTestSimpleAws):

    def test_init(self):
        filtered = [True, False]
        only_running = [True, False]
        conf_path = [None, CONF_PATH]
        for f, a, c in itertools.product(filtered, only_running, conf_path):
            try:
                m = AwsManager(c, filtered=f, only_running=a)
                self.assertIsInstance(m.conf, AwsManagerConfiguration)
            except ValueError:
                if c is None:
                    pass
                else:
                    raise

    def test_do_task(self):
        def _taskf_():
            run('mkdir -p ~/go/another/way')
        assert self.shared_instance is not None
        m = AwsManager(CONF_PATH)
        m.do_task(_taskf_, name=self.shared_instance_name)

    def test_get_instance_by_name(self):
        instance = self.shared_instance
        self.assertEqual(instance.tags['Name'], self.shared_instance_name)

    @attr('slow')
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
        name1 = self.get_instance_name('foo_test_1')
        i1 = m.launch_new_instance(name1)
        try:
            self.assertEqual(i1.update(), 'running')
        finally:
            i1.terminate()

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

    @attr('slow')
    def test_launch_new_instance_snapshot(self):
        m = AwsManager(CONF_PATH)
        i = m.launch_new_instance(self.get_instance_name('snapshot'), ebs_snapshot_id='snap-310873bc')
        iid = i.id
        try:
            volumes = m.conn.get_all_volumes()
            should_raise = True
            for volume in volumes:
                if volume.attach_data.instance_id == iid:
                    should_raise = False
                    break
            if should_raise:
                raise AssertionError('volume not attached')
        finally:
            i.terminate()
        m.wait_for_status(i, 'terminated')
        volumes = m.conn.get_all_volumes()
        for volume in volumes:
            if volume.attach_data.instance_id == iid:
                raise AssertionError('volume not terminated')

    def test_name_must_be_unique(self):
        m = AwsManager(CONF_PATH)
        assert self.shared_instance is not None
        try:
            with self.assertRaises(ValueError):
                i2 = m.launch_new_instance(self.shared_instance_name, wait=True)
        finally:
            try:
                i2.terminate()
            except UnboundLocalError:
                pass

    @attr('dev')
    def test_send_email(self):
        fromaddr = 'benkoziol@gmail.com'
        recipient = 'benkoziol@gmail.com'
        subject = 'OCGIS_AWS'
        body = 'This is some email content.'
        m = AwsManager(CONF_PATH)
        m.send_email(fromaddr, recipient, subject, body)


class TestAwsManagerConfiguration(AbstractTestSimpleAws):

    def test_init(self):
        with self.assertRaises(ValueError):
            AwsManagerConfiguration()
        c = AwsManagerConfiguration(conf_path=CONF_PATH)
        self.assertIsNotNone(c.aws_key_path)
        c = AwsManagerConfiguration(conf_path=CONF_PATH, aws_key_path='nowhere')
        self.assertEqual(c.aws_key_path, 'nowhere')